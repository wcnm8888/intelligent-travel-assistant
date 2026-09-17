import {
  act,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";
import { App } from "./App";
import {
  createF009Api,
  type AdvisorSnapshotDto,
  type PoiOptionDto,
  type PreplanningSessionDto,
} from "./f009Api";
import { f010SyntheticMapLoader } from "./f010SyntheticMapLoader";
import fixtureJson from "../../scripts/f019-fixture.json";

const fixture = fixtureJson as unknown as {
  options: PoiOptionDto[];
  advisor: AdvisorSnapshotDto;
  session: PreplanningSessionDto;
};
const [stay, first, second] = fixture.options;

function harness(nativeMapFailure = false) {
  let current = structuredClone(fixture.session);
  let advisor = structuredClone(fixture.advisor);
  const state = {
    failTurns: false,
    turnReply: null as string | null,
    turnGate: null as Promise<void> | null,
    failSearch: false,
    actions: [] as Array<{
      action: string;
      selection_context: PreplanningSessionDto["selection"];
    }>,
    turns: [] as string[],
  };
  const request = vi.fn<typeof fetch>(async (input, init) => {
    const url = String(input);
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    let value: unknown;
    if (
      (state.failSearch && url.includes("/pois?")) ||
      url.endsWith("/map-pins")
    )
      return new Response(
        JSON.stringify({
          error: { code: "offline_failure", message: "synthetic failure" },
        }),
        { status: 503 },
      );
    if (url === "/api/preplanning-sessions" && init?.method === "POST")
      value = current;
    else if (url.includes("/pois?")) {
      const purpose = new URL(url, "http://127.0.0.1").searchParams.get(
        "purpose",
      );
      value = {
        session_id: current.session_id,
        revision: current.revision,
        state: "needs_confirmation",
        page: 1,
        page_size: 20,
        has_more: false,
        items: fixture.options.filter((item) => item.purpose === purpose),
        calls: current.calls,
      };
    } else if (url.endsWith("/advisor-actions")) {
      state.actions.push(body);
      if (body.action === "accept")
        current = {
          ...current,
          revision: current.revision + 1,
          selection: body.selection_context,
        };
      advisor = {
        ...advisor,
        revision: current.revision,
        pending_suggestions: advisor.pending_suggestions.filter(
          (item) => item.suggestion_id !== body.suggestion_id,
        ),
      };
      value = advisor;
    } else if (url.endsWith("/advisor-turns")) {
      state.turns.push(body.message);
      await state.turnGate;
      if (state.failTurns)
        return new Response(
          JSON.stringify({
            error: {
              code: "advisor_unavailable",
              message: "synthetic failure",
            },
          }),
          { status: 503 },
        );
      value = {
        ...advisor,
        conversation: [
          ...advisor.conversation,
          { role: "user", text: body.message },
          ...(state.turnReply
            ? [{ role: "advisor", text: state.turnReply }]
            : []),
        ],
      };
    } else if (url.endsWith("/advisor")) value = advisor;
    else if (url === `/api/preplanning-sessions/${current.session_id}`)
      value = current;
    else throw new Error(`Unexpected mock request: ${url}`);
    return new Response(JSON.stringify(value), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  render(
    <App
      f009Api={createF009Api(request)}
      f009MapLoader={
        nativeMapFailure
          ? async () => {
              throw new Error("offline loader failure");
            }
          : f010SyntheticMapLoader
      }
      syntheticSelectionMap={!nativeMapFailure}
    />,
  );
  return { state, request };
}

async function reachSelection() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "查看地图与地点" }));
  await user.click(await screen.findByRole("button", { name: "选择住宿" }));
  const editor = within(screen.getByRole("dialog", { name: "编辑住宿与地点" }));
  await user.click(editor.getAllByRole("button", { name: "搜索" })[0]);
  await user.click(
    await editor.findByRole("button", { name: new RegExp(stay.name) }),
  );
  await user.click(editor.getAllByRole("button", { name: "搜索" })[1]);
  await editor.findByRole("button", { name: new RegExp(first.name) });
  await user.click(editor.getByRole("button", { name: "返回选点" }));
  return user;
}

const list = () => within(screen.getByRole("region", { name: "地点清单" }));
const advice = () =>
  within(screen.getByRole("complementary", { name: "旅行顾问" }));
const listCard = (name: string) =>
  within(list().getByRole("article", { name }));
const adviceCard = (name: string) =>
  within(advice().getByRole("article", { name }));

test("UI8 R1 map return reveals filtered target and repeats without selecting", async () => {
  const h = harness();
  const user = await reachSelection();
  const search = list().getByRole("textbox");
  await user.type(search, first.name);
  expect(
    list().queryByRole("article", { name: second.name }),
  ).not.toBeInTheDocument();
  const marker = screen.getByRole("button", {
    name: `地图定位：${second.name}`,
  });
  await user.click(marker);
  expect(list().getByRole("article", { name: second.name })).toHaveFocus();
  expect(search).toHaveValue("");
  await user.type(search, first.name);
  await user.click(marker);
  expect(list().getByRole("article", { name: second.name })).toHaveFocus();
  expect(screen.getByText(/已选景点\s+0/)).toBeVisible();
  expect(h.state.actions).toHaveLength(0);
});

test("UI8 R1 category search does not filter returned place names by the query", async () => {
  const h = harness();
  const user = await reachSelection();
  const search = list().getByRole("textbox");
  await user.type(search, "自然景点{Enter}");
  await waitFor(() =>
    expect(
      h.request.mock.calls.some(([url]) =>
        String(url).includes(encodeURIComponent("自然景点")),
      ),
    ).toBe(true),
  );
  expect(list().getByRole("article", { name: first.name })).toBeVisible();
  expect(list().getByRole("article", { name: second.name })).toBeVisible();
});

test("UI8 R2 missing lodging notice belongs to the active editor", async () => {
  harness();
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: "查看地图与地点" }));
  await user.click(await screen.findByRole("button", { name: "选择住宿" }));
  const editor = within(screen.getByRole("dialog", { name: "编辑住宿与地点" }));
  await user.click(editor.getAllByRole("button", { name: "搜索" })[1]);
  await user.click(
    await editor.findByRole("button", { name: new RegExp(first.name) }),
  );
  await user.click(
    editor.getByRole("button", { name: "已选好，补充旅行信息" }),
  );
  expect(editor.getByRole("alert")).toHaveTextContent("请先从列表确认住宿锚点");
  expect(screen.getAllByRole("alert")).toHaveLength(1);
});

test.each(["search", "pin"])(
  "UI8 R2 %s failure is announced inside editor without losing selection",
  async (kind) => {
    const h = harness();
    const user = await reachSelection();
    await user.click(
      listCard(first.name).getByRole("button", { name: "加入已选" }),
    );
    await user.click(screen.getByRole("button", { name: "更换住宿" }));
    const editor = within(
      screen.getByRole("dialog", { name: "编辑住宿与地点" }),
    );
    if (kind === "search") {
      h.state.failSearch = true;
      await user.click(editor.getAllByRole("button", { name: "搜索" })[1]);
    } else {
      await user.click(editor.getByRole("radio", { name: "地图上选择" }));
      await user.click(editor.getByRole("button", { name: "确认这个位置" }));
    }
    expect(await editor.findByRole("alert")).toHaveTextContent(
      "本地请求暂时无法完成",
    );
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    await user.click(editor.getByRole("button", { name: "返回选点" }));
    expect(screen.getByRole("button", { name: "更换住宿" })).toHaveFocus();
    expect(screen.getByText(/已选景点\s+1/)).toBeVisible();
  },
);

test("UI8 R3 failed native map retains the section navigation target", async () => {
  harness(true);
  await reachSelection();
  const region = screen.getByRole("region", { name: "地点地图" });
  expect(region).toHaveAttribute("data-state", "unavailable");
  const link = screen.getByRole("link", { name: "地点地图", hidden: true });
  expect(link).toHaveAttribute("href", `#${region.id}`);
  expect(region).toHaveAttribute("tabindex", "-1");
  expect(document.querySelectorAll("#f019-map-region")).toHaveLength(1);
});

test("frozen normal state, mixed local/advisor selection and duplicate confirmation preserve identity", async () => {
  const h = harness();
  const user = await reachSelection();
  expect(screen.getByText("2 条建议待确认")).toBeVisible();
  expect(screen.getByText(/已选景点\s+0/)).toBeVisible();
  expect(
    listCard(first.name).getByRole("button", { name: "加入已选" }),
  ).toBeEnabled();
  expect(screen.getByRole("button", { name: "发送给旅行顾问" })).toBeDisabled();
  expect(
    screen.queryByRole("heading", { name: "最近对话" }),
  ).not.toBeInTheDocument();
  expect(document.querySelector("button button")).toBeNull();
  fireEvent.click(screen.getByRole("link", { name: "跳到地图优先规划" }));
  expect(
    screen.getByRole("heading", { name: "杭州，先选出想去的地方" }),
  ).toHaveFocus();
  await user.click(
    listCard(first.name).getByRole("button", { name: "加入已选" }),
  );
  expect(h.state.actions).toHaveLength(0);
  expect(screen.getByText("2 条建议待确认")).toBeVisible();
  await user.click(
    adviceCard(second.name).getByRole("button", { name: "加入已选" }),
  );
  await waitFor(() => expect(screen.getByText(/已选景点\s+2/)).toBeVisible());
  expect(
    h.state.actions[0].selection_context?.pois.map((item) => item.location_id),
  ).toEqual([first.location_id, second.location_id]);
  await user.click(
    adviceCard(first.name).getByRole("button", { name: "确认已选" }),
  );
  await waitFor(() => expect(screen.getByText("0 条建议待确认")).toBeVisible());
  expect(h.state.actions[1].selection_context?.pois).toHaveLength(2);
  expect(
    listCard(first.name).getByRole("button", { name: "已加入" }),
  ).toBeDisabled();
});

test("ignore and filtering preserve stable numbers without selecting; next stage is gated", async () => {
  const h = harness();
  const user = await reachSelection();
  await user.click(screen.getByRole("button", { name: /03\s+比较方案/ }));
  expect(screen.queryByText("保存信息并进入空间预检")).not.toBeInTheDocument();
  await user.click(
    adviceCard(first.name).getByRole("button", { name: "忽略" }),
  );
  await waitFor(() => expect(screen.getByText("1 条建议待确认")).toBeVisible());
  expect(h.state.actions[0].selection_context).toBeNull();
  expect(screen.getByText(/已选景点\s+0/)).toBeVisible();
  const search = list().getByRole("textbox");
  await user.type(search, second.name);
  expect(
    list().queryByRole("article", { name: first.name }),
  ).not.toBeInTheDocument();
  expect(listCard(second.name).getByRole("heading")).toHaveTextContent(
    `2 · ${second.name}`,
  );
  await user.clear(search);
  expect(listCard(first.name).getByRole("heading")).toHaveTextContent(
    `1 · ${first.name}`,
  );
});

test("map focus works in both directions, repeated focus resets zoom, fit restores positions", async () => {
  const h = harness();
  const user = await reachSelection();
  const marker = screen.getByRole("button", {
    name: `地图定位：${first.name}`,
  });
  const originalLeft = marker.style.left;
  await user.click(
    listCard(first.name).getByRole("button", { name: "地图查看" }),
  );
  await waitFor(() => expect(marker).toHaveFocus());
  expect(marker.style.left).not.toBe(originalLeft);
  await user.click(screen.getByRole("button", { name: "放大地图" }));
  await user.click(
    adviceCard(first.name).getByRole("button", { name: "地图查看" }),
  );
  await waitFor(() => expect(marker).toHaveFocus());
  expect(screen.getByRole("region", { name: "地点地图" })).toHaveAttribute(
    "data-focus-sequence",
    "2",
  );
  await user.click(marker);
  expect(list().getByRole("article", { name: first.name })).toHaveFocus();
  await user.click(screen.getByRole("button", { name: "查看全部" }));
  expect(marker.style.left).toBe(originalLeft);
  expect(h.state.actions).toHaveLength(0);
  expect(screen.getByText(/已选景点\s+0/)).toBeVisible();
});

test("500-length boundary, IME, rapid submits and failed draft retention", async () => {
  const h = harness();
  const user = await reachSelection();
  const textbox = screen.getByLabelText("你的补充");
  const form = textbox.closest("form")!;
  fireEvent.change(textbox, { target: { value: "   " } });
  fireEvent.submit(form);
  fireEvent.change(textbox, { target: { value: "好".repeat(501) } });
  fireEvent.submit(form);
  expect(h.state.turns).toHaveLength(0);
  fireEvent.change(textbox, { target: { value: "好".repeat(500) } });
  fireEvent.compositionStart(textbox);
  fireEvent.submit(form);
  expect(h.state.turns).toHaveLength(0);
  fireEvent.compositionEnd(textbox);
  await act(async () => {
    fireEvent.submit(form);
    fireEvent.submit(form);
  });
  expect(h.state.turns).toHaveLength(1);
  expect(h.state.turns[0]).toHaveLength(500);
  await waitFor(() => expect(textbox).toHaveValue(""));
  h.state.failTurns = true;
  await user.type(textbox, "保留我的补充");
  await user.click(screen.getByRole("button", { name: "发送给旅行顾问" }));
  await screen.findByRole("alert");
  expect(textbox).toHaveValue("保留我的补充");
  expect(screen.getByRole("button", { name: "发送给旅行顾问" })).toBeEnabled();
});

test("rapid list adds remain unique and history is available through keyboard", async () => {
  harness();
  const user = await reachSelection();
  const add = listCard(first.name).getByRole("button", { name: "加入已选" });
  act(() => {
    fireEvent.click(add);
    fireEvent.click(add);
  });
  expect(screen.getByText(/已选景点\s+1/)).toBeVisible();
  const history = screen.getByRole("button", { name: /查看对话记录/ });
  history.focus();
  await user.keyboard("{Enter}");
  expect(screen.getByRole("heading", { name: "最近对话" })).toBeVisible();
  expect(
    within(screen.getByRole("region", { name: "对话与偏好" })).getByText(
      fixture.advisor.conversation[0].text,
      { selector: "p" },
    ),
  ).toBeVisible();
  await user.click(screen.getByRole("button", { name: "少走路" }));
  expect(screen.getByLabelText("你的补充")).toHaveValue("少走路");
  expect(screen.getByText("已确认偏好 0")).toBeVisible();
});

test("advisor replies announce outside collapsed history and restore only composer focus", async () => {
  const h = harness();
  const user = await reachSelection();
  const textbox = screen.getByLabelText("你的补充");
  h.state.turnReply = "已为你整理新的自然景点建议。";
  let finishTurn!: () => void;
  h.state.turnGate = new Promise<void>((resolve) => {
    finishTurn = resolve;
  });
  await user.type(textbox, "想看自然景点");
  await user.click(screen.getByRole("button", { name: "发送给旅行顾问" }));
  await act(async () => {
    finishTurn();
  });
  const status = advice().getByRole("status", { name: "顾问最新回复" });
  expect(status).toHaveAttribute("aria-live", "polite");
  expect(status).toHaveAttribute("aria-atomic", "true");
  expect(status).toHaveTextContent(h.state.turnReply);
  expect(status).toHaveTextContent("2 条建议待确认");
  expect(status).not.toHaveTextContent(fixture.advisor.conversation[0].text);
  expect(
    screen.queryByRole("heading", { name: "最近对话" }),
  ).not.toBeInTheDocument();
  expect(textbox).toHaveFocus();

  h.state.turnReply = "这轮建议已更新。";
  h.state.turnGate = new Promise<void>((resolve) => {
    finishTurn = resolve;
  });
  await user.type(textbox, "再补充一个想法");
  await user.click(screen.getByRole("button", { name: "发送给旅行顾问" }));
  const search = list().getByRole("textbox");
  await user.click(search);
  await act(async () => {
    finishTurn();
  });
  expect(status).toHaveTextContent(h.state.turnReply);
  expect(status).not.toHaveTextContent("已为你整理新的自然景点建议。");
  expect(search).toHaveFocus();
});
