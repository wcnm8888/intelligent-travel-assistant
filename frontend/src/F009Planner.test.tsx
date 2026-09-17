import {
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, test, vi } from "vitest";

import { App } from "./App";
import type {
  AdvisorSnapshotDto,
  F009Api,
  MapPlanDto,
  PoiOptionDto,
  PreflightDto,
  PreflightV6Dto,
  PreplanningSessionDto,
  TripPlanV5ResponseDto,
} from "./f009Api";
import { F009ClientError } from "./f009Api";

const SESSION_ID = "70000000-0000-4000-8000-000000000001";
const LODGING_ID = "70000000-0000-4000-8000-000000000002";
const WEST_LAKE_ID = "70000000-0000-4000-8000-000000000003";
const LINGYIN_ID = "70000000-0000-4000-8000-000000000004";
const WEST_LAKE_AREA_ID = "70000000-0000-4000-8000-000000000014";
const JOB_ID = "70000000-0000-4000-8000-000000000005";
const PLAN_ID = "70000000-0000-4000-8000-000000000006";

function option(
  locationId: string,
  name: string,
  purpose: "visit" | "accommodation",
  longitude: number,
): PoiOptionDto {
  return {
    location_id: locationId,
    provider: "amap",
    provider_place_id: `provider-${locationId}`,
    name,
    address: "杭州市",
    city_adcode: "330100",
    district_adcode: "330102",
    category_code: purpose === "accommodation" ? "hotel" : "scenic_area",
    category_label: purpose === "accommodation" ? "住宿服务" : "风景名胜",
    coordinate_gcj02: { longitude, latitude: 30.25 },
    purpose,
    scope_kind: "point",
    confirmation_status: "verified",
  };
}

const lodging = option(LODGING_ID, "龙翔桥住宿锚点", "accommodation", 120.16);
const westLake = option(WEST_LAKE_ID, "西湖断桥", "visit", 120.17);
const lingyin = option(LINGYIN_ID, "灵隐寺", "visit", 120.11);
const westLakeArea: PoiOptionDto = {
  ...option(WEST_LAKE_AREA_ID, "西湖风景名胜区", "visit", 120.15),
  scope_kind: "complex",
  confirmation_status: "representative_required",
};

const advisorSnapshot: AdvisorSnapshotDto = {
  advisor_version: "1",
  session_id: SESSION_ID,
  revision: 0,
  phase: "interview",
  conversation: [],
  confirmed_preferences: {
    walking_tolerance: null,
    crowd_tolerance: null,
    day_start: null,
    food_preferences: [],
    budget_flexibility: null,
    party_notes: [],
  },
  pending_suggestions: [],
  question: "你更在意少走路，还是避开拥挤？",
  safety_summary: "已确认 0 项偏好，发现 0 个待确认地点。",
};

function session(
  selection: PreplanningSessionDto["selection"] = null,
): PreplanningSessionDto {
  return {
    session_version: "1",
    session_id: SESSION_ID,
    revision: selection ? 1 : 0,
    state: selection ? "needs_confirmation" : "draft",
    trip: {
      city: "杭州",
      start_date: "2026-10-01",
      end_date: "2026-10-02",
      travelers: 2,
      total_budget: { amount: "3000", currency: "CNY" },
      preferences: { interests: [], free_text: "", hard_constraints: [] },
      pace: "balanced",
      transport_modes: ["public_transit", "walking"],
      day_windows: [
        { day_offset: 0, start_time: "09:00:00", end_time: "20:00:00" },
        { day_offset: 1, start_time: "09:00:00", end_time: "20:00:00" },
      ],
    },
    city_adcode: "330100",
    city_name: "杭州市",
    selection,
    calls: { poi_search: 0, reverse_geocode: 0, route: 0, total: 0 },
    created_at: "2026-09-13T06:00:00Z",
    expires_at: "2026-09-13T06:30:00Z",
    absolute_expires_at: "2026-09-13T08:00:00Z",
  };
}

const routes = [
  {
    route_id: "70000000-0000-4000-8000-000000000010",
    origin_location_id: LODGING_ID,
    destination_location_id: WEST_LAKE_ID,
    mode: "walking" as const,
    straight_line_meters: 1200,
    distance_meters: 1500,
    duration_minutes: 20,
  },
  {
    route_id: "70000000-0000-4000-8000-000000000011",
    origin_location_id: WEST_LAKE_ID,
    destination_location_id: LODGING_ID,
    mode: "walking" as const,
    straight_line_meters: 1200,
    distance_meters: 1500,
    duration_minutes: 20,
  },
];

function fakeApi(): F009Api {
  let selection: NonNullable<PreplanningSessionDto["selection"]> | null = null;
  const preflight: PreflightDto = {
    session_id: SESSION_ID,
    revision: 1,
    state: "feasible",
    feasibility_id: "70000000-0000-4000-8000-000000000012",
    days: [
      {
        local_date: "2026-10-01",
        stops: [
          {
            location_id: WEST_LAKE_ID,
            route_anchor_location_id: WEST_LAKE_ID,
            name: "西湖断桥",
            category: "风景名胜",
            importance: "must_visit",
            expected_duration_minutes: 90,
            start_time: "09:35:00",
            end_time: "11:05:00",
            preferred_day_satisfied: true,
            source: "user_selected",
          },
        ],
        routes,
        total_transport_minutes: 40,
      },
      {
        local_date: "2026-10-02",
        stops: [
          {
            location_id: LINGYIN_ID,
            route_anchor_location_id: LINGYIN_ID,
            name: "灵隐寺",
            category: "风景名胜",
            importance: "must_visit",
            expected_duration_minutes: 90,
            start_time: "09:35:00",
            end_time: "11:05:00",
            preferred_day_satisfied: true,
            source: "user_selected",
          },
        ],
        routes: routes.map((route, index) => ({
          ...route,
          route_id: `70000000-0000-4000-8000-00000000002${index}`,
          destination_location_id: index === 0 ? LINGYIN_ID : LODGING_ID,
          origin_location_id: index === 0 ? LODGING_ID : LINGYIN_ID,
        })),
        total_transport_minutes: 40,
      },
    ],
    conflicts: [],
    calls: { poi_search: 2, reverse_geocode: 0, route: 6, total: 8 },
  };
  const result: TripPlanV5ResponseDto = {
    response_version: "5",
    job_id: JOB_ID,
    trace_id: "70000000-0000-4000-8000-000000000007",
    client_request_id: "70000000-0000-4000-8000-000000000008",
    status: "partial",
    attempt: 1,
    request_summary: {
      request_version: "5",
      city: "杭州",
      start_date: "2026-10-01",
      end_date: "2026-10-02",
      travelers: 2,
      budget: { amount: "3000.00", currency: "CNY" },
      selected_poi_count: 2,
    },
    plan: {
      plan_id: PLAN_ID,
      plan_format_version: "5",
      city_adcode: "330100",
      start_date: "2026-10-01",
      end_date: "2026-10-02",
      accommodation: {
        mode: "exact_poi",
        label: lodging.name,
        confidence: "exact",
        semantic_location_id: LODGING_ID,
        route_anchor_location_id: LODGING_ID,
      },
      locations: [lodging, westLake, lingyin].map((item) => ({
        location_id: item.location_id,
        name: item.name,
        category: item.category_label,
        district_adcode: item.district_adcode,
        source:
          item.location_id === LODGING_ID ? "accommodation" : "user_selected",
      })),
      days: preflight.days.map((day) => ({
        local_date: day.local_date,
        accommodation_location_id: LODGING_ID,
        stops: day.stops.map((stop, index) => ({
          location_id: stop.location_id,
          visit_order: index + 1,
          start_time: stop.start_time,
          end_time: stop.end_time,
          importance: stop.importance,
          narrative: null,
        })),
        routes: day.routes.map((route) => ({
          route_id: route.route_id,
          origin_location_id: route.origin_location_id,
          destination_location_id: route.destination_location_id,
          mode: route.mode,
          distance_meters: route.distance_meters,
          duration_minutes: route.duration_minutes,
        })),
        pace_note: null,
        rationale: null,
      })),
      global_notes: [],
    },
    conflicts: [],
    warnings: ["确定性计划已保留；模型说明不可用。"],
    errors: [
      {
        code: "model_output_invalid",
        message: "DeepSeek 说明未通过受约束校验；确定性行程与路线已保留。",
        field: null,
        provider: "deepseek",
        diagnostic_code: "narrative_repair_identity_invalid",
        retryable: false,
      },
    ],
    retryable: true,
    created_at: "2026-09-13T07:00:00Z",
    updated_at: "2026-09-13T07:00:00Z",
  };
  const mapPlan: MapPlanDto = {
    map_version: "1",
    job_id: JOB_ID,
    plan_id: PLAN_ID,
    coordinate_system: "gcj02",
    accommodation: {
      location_id: LODGING_ID,
      name: lodging.name,
      coordinate: lodging.coordinate_gcj02,
      visit_order: null,
    },
    days: preflight.days.map((day, index) => ({
      local_date: day.local_date,
      color_token: `day-${index + 1}`,
      markers: day.stops.map((stop, stopIndex) => ({
        location_id: stop.location_id,
        name: stop.name,
        coordinate:
          stopIndex === 0
            ? westLake.coordinate_gcj02
            : lingyin.coordinate_gcj02,
        visit_order: stopIndex + 1,
      })),
      routes: day.routes.map((route) => ({
        route_id: route.route_id,
        origin_location_id: route.origin_location_id,
        destination_location_id: route.destination_location_id,
        mode: route.mode,
        distance_meters: route.distance_meters,
        duration_minutes: route.duration_minutes,
        points: [lodging.coordinate_gcj02, westLake.coordinate_gcj02],
      })),
    })),
    warnings: [],
  };
  const preflightV6: PreflightV6Dto = {
    response_version: "6",
    session_id: SESSION_ID,
    revision: 1,
    state: preflight.state,
    feasibility_set_id: preflight.feasibility_id,
    options: [
      {
        option_id: "70000000-0000-4000-8000-000000000013",
        kind: "less_transport",
        title: "交通更少",
        explanation: "优先减少总交通时间。",
        days: preflight.days,
        omitted_location_ids: [],
        total_transport_minutes: 28,
        preferred_day_deviation: 0,
        preference_coverage_score: 100,
        weather_status: "not_covered",
        weather_message: "天气尚不可核验",
      },
    ],
    conflicts: preflight.conflicts,
    calls: preflight.calls,
  };
  const resultV6 = {
    ...result,
    response_version: "6" as const,
    request_summary: {
      ...result.request_summary,
      request_version: "6" as const,
    },
    plan: result.plan
      ? {
          ...result.plan,
          plan_format_version: "6" as const,
          selected_option_id: preflightV6.options[0].option_id,
          option_kind: "less_transport" as const,
          weather_status: "not_covered" as const,
          weather_message: "天气尚不可核验",
        }
      : null,
  };
  return {
    createSession: vi.fn(async () => session()),
    getSession: vi.fn(async () => session(selection)),
    updateTrip: vi.fn(async (_sessionId, _revision, nextTrip) => ({
      ...session(),
      revision: 1,
      trip: nextTrip,
    })),
    searchPois: vi.fn(async (_sessionId, purpose) => ({
      session_id: SESSION_ID,
      revision: 0,
      state: "needs_confirmation" as const,
      page: 1,
      page_size: 20,
      has_more: false,
      items: purpose === "accommodation" ? [lodging] : [westLake, lingyin],
      calls: {
        poi_search: purpose === "accommodation" ? 1 : 2,
        reverse_geocode: 0,
        route: 0,
        total: purpose === "accommodation" ? 1 : 2,
      },
    })),
    createMapPin: vi.fn(),
    updateSelection: vi.fn(async (_sessionId, _revision, nextSelection) => {
      selection = nextSelection;
      return { ...session(selection), revision: 2 };
    }),
    preflight: vi.fn(async () => preflight),
    preflightV6: vi.fn(async () => preflightV6),
    applyRecoveryAction: vi.fn(async () => session(selection)),
    createPlan: vi.fn(async () => result),
    createPlanV6: vi.fn(async () => resultV6),
    retryNarrative: vi.fn(async () => ({
      ...resultV6,
      status: "ready" as const,
      warnings: [],
      errors: [],
      retryable: false,
      plan: resultV6.plan
        ? {
            ...resultV6.plan,
            days: resultV6.plan.days.map((day) => ({
              ...day,
              pace_note: "按已冻结顺序从容游览。",
              rationale: "保持已验证路线与当天节奏。",
              stops: day.stops.map((stop) => ({
                ...stop,
                narrative: "留意现场指引。",
              })),
            })),
          }
        : null,
    })),
    readMap: vi.fn(async () => mapPlan),
  };
}

test("offline list journey survives map loader failure and preserves selected IDs", async () => {
  const user = userEvent.setup();
  const api = fakeApi();
  render(
    <App
      f009Api={api}
      f009MapLoader={() =>
        Promise.reject(new Error("synthetic loader failure"))
      }
      createClientRequestId={() => "70000000-0000-4000-8000-000000000008"}
    />,
  );

  expect(
    screen.getByRole("heading", { name: "正式地点列表" }),
  ).toBeInTheDocument();
  expect(screen.getByRole("region", { name: "地点地图" })).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: "经典文字规划" }),
  ).not.toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "查看地图与地点" }));
  await screen.findByText("地图当前不可用");
  expect(screen.getByText(/列表仍可完成地点选择/)).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "选择住宿" }));
  await user.click(screen.getAllByRole("button", { name: "搜索" })[0]);
  await user.click(
    await screen.findByRole("button", { name: /龙翔桥住宿锚点/ }),
  );
  await user.click(screen.getAllByRole("button", { name: "搜索" })[1]);
  await user.click(await screen.findByRole("button", { name: /西湖断桥/ }));
  await user.click(screen.getByRole("button", { name: /灵隐寺/ }));
  await user.click(
    screen.getByRole("button", { name: "已选好，补充旅行信息" }),
  );
  const detailsHeading = screen.getByText(/为已选的 2 个地点补充旅行信息/);
  expect(detailsHeading).toBeInTheDocument();
  expect(detailsHeading).toHaveFocus();
  expect(screen.queryByText("二选一组")).not.toBeInTheDocument();
  expect(screen.queryByText("联合游览组")).not.toBeInTheDocument();
  await user.click(screen.getByRole("radio", { name: /与其他地点一起游览/ }));
  await user.click(screen.getByRole("checkbox", { name: "西湖断桥" }));
  await user.click(screen.getByRole("checkbox", { name: "灵隐寺" }));
  await user.click(screen.getByRole("button", { name: "应用这个关系" }));
  expect(screen.getAllByText("一起游览")).toHaveLength(3);
  await user.click(screen.getByRole("button", { name: "返回选点" }));
  await user.click(screen.getByRole("button", { name: "更换住宿" }));
  expect(
    screen.getByRole("button", { name: /西湖断桥/ }).closest("li"),
  ).toHaveAttribute("data-selected", "true");
  await user.click(
    screen.getByRole("button", { name: "已选好，补充旅行信息" }),
  );
  await user.click(
    screen.getByRole("button", { name: "保存信息并进入空间预检" }),
  );

  await waitFor(() => expect(api.updateTrip).toHaveBeenCalledTimes(1));
  await waitFor(() => expect(api.updateSelection).toHaveBeenCalledTimes(1));
  const selection = vi.mocked(api.updateSelection).mock.calls[0][2];
  expect(selection.accommodation.route_anchor_location_id).toBe(LODGING_ID);
  expect(selection.pois.map((item) => item.location_id)).toEqual([
    WEST_LAKE_ID,
    LINGYIN_ID,
  ]);
  expect(selection.pois[0].visit_group_id).toMatch(/^together-/);
  expect(selection.pois[1].visit_group_id).toBe(
    selection.pois[0].visit_group_id,
  );

  await user.click(screen.getByRole("button", { name: "运行空间预检" }));
  expect(await screen.findByText("预检可行")).toBeInTheDocument();
  expect(screen.getByLabelText("选点与安排摘要")).toHaveTextContent(
    "已选择地点2实际安排地点2未采用地点0",
  );
  await user.click(screen.getByRole("button", { name: "确认方案并生成行程" }));
  expect(await screen.findByText("行程已生成")).toBeInTheDocument();
  expect(screen.queryByText(/V5 计划/)).not.toBeInTheDocument();
  expect(screen.getByText("AI 游览提示暂不可用")).toBeInTheDocument();
  expect(
    screen.getByText(/地点、日期、时间、路线和这份计划仍然有效/),
  ).toBeInTheDocument();
  const diagnostic = screen.getByText("查看技术详情").closest("details");
  expect(diagnostic).not.toHaveAttribute("open");
  expect(diagnostic).toHaveTextContent("narrative_repair_identity_invalid");
  expect(screen.getAllByText("从住宿出发")).toHaveLength(2);
  expect(screen.getAllByText("返回住宿")).toHaveLength(2);
  expect(screen.getAllByText(/1\.5 公里/).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/西湖断桥/).length).toBeGreaterThan(0);
  await user.click(screen.getByRole("button", { name: "重试 AI 游览提示" }));
  await waitFor(() => expect(api.retryNarrative).toHaveBeenCalledTimes(1));
  expect(screen.queryByText("AI 游览提示暂不可用")).not.toBeInTheDocument();
  expect(screen.getAllByText("旅行顾问建议")).toHaveLength(2);
});

test("advisor drawer shows bounded conversation, quick replies, preferences, and collapse", async () => {
  const user = userEvent.setup();
  const api = fakeApi();
  api.getAdvisor = vi.fn(async () => advisorSnapshot);
  api.advisorTurn = vi.fn(
    async (_sessionId, _revision, _requestId, message) => ({
      ...advisorSnapshot,
      conversation: [
        { role: "user" as const, text: message },
        {
          role: "advisor" as const,
          text: "已记下少走路，你是否也想避开拥挤？",
        },
      ],
      confirmed_preferences: {
        ...advisorSnapshot.confirmed_preferences,
        walking_tolerance: "low" as const,
        party_notes: ["老人同行"],
      },
      question: "已记下少走路，你是否也想避开拥挤？",
      safety_summary: "已确认 2 项偏好，发现 0 个待确认地点。",
    }),
  );
  renderPlanner(api);

  await user.click(screen.getByRole("button", { name: "查看地图与地点" }));
  expect(
    await screen.findByRole("heading", { name: "旅行顾问" }),
  ).toBeVisible();
  expect(screen.getByText("你更在意少走路，还是避开拥挤？")).toBeVisible();
  await user.click(screen.getByRole("button", { name: "少走路" }));
  expect(screen.getByLabelText("你的补充")).toHaveValue("少走路");
  await user.click(screen.getByRole("button", { name: "发送给旅行顾问" }));

  expect(
    await screen.findByText("已记下少走路，你是否也想避开拥挤？"),
  ).toBeVisible();
  expect(screen.getByText("步行承受度：低")).toBeVisible();
  expect(screen.getByText("同行：老人同行")).toBeVisible();
  expect(
    screen.getByRole("button", { name: "先推荐自然景点，其他都灵活" }),
  ).toBeVisible();
  const toggle = screen.getByRole("button", { name: "收起" });
  await user.click(toggle);
  expect(screen.queryByText("最近对话")).not.toBeInTheDocument();
  expect(screen.getByRole("button", { name: "打开顾问" })).toHaveAttribute(
    "aria-expanded",
    "false",
  );
});

test("advisor discovery request searches first and surfaces suggestions before more questions", async () => {
  const user = userEvent.setup();
  const api = fakeApi();
  api.getAdvisor = vi.fn(async () => advisorSnapshot);
  api.advisorTurn = vi.fn(
    async (_sessionId, _revision, _requestId, message) => ({
      ...advisorSnapshot,
      phase: "curation" as const,
      conversation: [
        { role: "user" as const, text: message },
        {
          role: "advisor" as const,
          text: "先看看这些自然景点，其他偏好可以以后再补充。",
        },
      ],
      pending_suggestions: [
        {
          suggestion_id: "70000000-0000-4000-8000-000000000016",
          kind: "poi" as const,
          title: "考虑 西湖断桥",
          reason: "来自已验证的自然景点候选。",
          preference_patch: null,
          location_id: WEST_LAKE_ID,
          location_name: "西湖断桥",
          category: "风景名胜",
        },
      ],
      question: "先看看这些自然景点，其他偏好可以以后再补充。",
      safety_summary: "已确认 0 项偏好，发现 1 个待确认地点。",
    }),
  );
  renderPlanner(api);

  await user.click(screen.getByRole("button", { name: "查看地图与地点" }));
  await user.click(
    screen.getByRole("button", { name: "先推荐自然景点，其他都灵活" }),
  );
  await user.click(screen.getByRole("button", { name: "发送给旅行顾问" }));

  expect(api.searchPois).toHaveBeenCalledWith(SESSION_ID, "visit", "自然景点");
  expect(await screen.findByText("1 条建议，等你确认")).toBeVisible();
  expect(screen.getAllByText("1 · 西湖断桥")).toHaveLength(2);
  await user.click(screen.getByRole("button", { name: /查看对话记录/ }));
  expect(
    within(screen.getByRole("region", { name: "对话与偏好" })).getByText(
      /其他偏好可以以后再补充/,
    ),
  ).toBeVisible();
  expect(
    within(
      within(screen.getByRole("region", { name: "地点清单" })).getByRole(
        "article",
        { name: "西湖断桥" },
      ),
    ).getByRole("button", { name: "加入已选" }),
  ).toBeVisible();
});

test("area POI automatically searches and clearly completes a route anchor choice", async () => {
  const user = userEvent.setup();
  const api = fakeApi();
  api.searchPois = vi.fn(async (_sessionId, purpose, keywords) => ({
    session_id: SESSION_ID,
    revision: 0,
    state: "needs_confirmation" as const,
    page: 1,
    page_size: 20,
    has_more: false,
    items:
      purpose === "accommodation"
        ? [lodging]
        : keywords.includes("入口")
          ? [westLake]
          : [westLakeArea],
    calls: {
      poi_search: purpose === "accommodation" ? 1 : 2,
      reverse_geocode: 0,
      route: 0,
      total: purpose === "accommodation" ? 1 : 2,
    },
  }));
  renderPlanner(api);

  await user.click(screen.getByRole("button", { name: "查看地图与地点" }));
  await user.click(screen.getByRole("button", { name: "选择住宿" }));
  await user.click(screen.getAllByRole("button", { name: "搜索" })[0]);
  await user.click(
    await screen.findByRole("button", { name: /龙翔桥住宿锚点/ }),
  );
  await user.click(screen.getAllByRole("button", { name: "搜索" })[1]);
  await user.click(
    await screen.findByRole("button", { name: /西湖风景名胜区/ }),
  );

  expect(
    await screen.findByText(/为“西湖风景名胜区”选择一个具体入口/),
  ).toBeVisible();
  expect(api.searchPois).toHaveBeenCalledWith(
    SESSION_ID,
    "visit",
    "西湖风景名胜区 入口",
  );
  await user.click(await screen.findByRole("button", { name: /西湖断桥/ }));
  expect(screen.queryByText(/选择一个具体入口/)).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: /西湖风景名胜区/ }),
  ).toHaveTextContent("已选择，路线入口已确认");

  await user.click(
    screen.getByRole("button", { name: "已选好，补充旅行信息" }),
  );
  await user.click(
    screen.getByRole("button", { name: "保存信息并进入空间预检" }),
  );
  await waitFor(() => expect(api.updateSelection).toHaveBeenCalledTimes(1));
  const saved = vi.mocked(api.updateSelection).mock.calls[0][2];
  expect(saved.pois[0]).toMatchObject({
    location_id: WEST_LAKE_AREA_ID,
    route_anchor_location_id: WEST_LAKE_ID,
  });
});

test("plan option cards expose daily distribution when total transport ties", async () => {
  const user = userEvent.setup();
  const api = fakeApi();
  const base = await api.preflightV6(SESSION_ID, 1);
  const first = base.options[0];
  const lessTransport = {
    ...first,
    days: first.days.map((day, index) => ({
      ...day,
      total_transport_minutes: index === 0 ? 60 : 20,
    })),
    total_transport_minutes: 80,
  };
  const relaxed = {
    ...first,
    option_id: "70000000-0000-4000-8000-000000000015",
    kind: "relaxed_pace" as const,
    title: "节奏更轻松",
    explanation: "总交通相同，但每天负担更均匀。",
    days: first.days.map((day) => ({
      ...day,
      total_transport_minutes: 40,
    })),
    total_transport_minutes: 80,
  };
  vi.mocked(api.preflightV6).mockResolvedValue({
    ...base,
    options: [lessTransport, relaxed],
  });
  renderPlanner(api);

  await reachTripDetails(user);
  await user.click(
    screen.getByRole("button", { name: "保存信息并进入空间预检" }),
  );
  await user.click(screen.getByRole("button", { name: "运行空间预检" }));

  expect(
    await screen.findByText("比较 2 个具有不同取舍的可行方案"),
  ).toBeVisible();
  const transportCard = screen.getByText("交通更少").closest("label");
  const relaxedCard = screen.getByText("节奏更轻松").closest("label");
  expect(transportCard).not.toBeNull();
  expect(relaxedCard).not.toBeNull();
  expect(
    within(transportCard as HTMLElement).getByText(/最忙一天交通 60 分钟/),
  ).toBeVisible();
  expect(
    within(relaxedCard as HTMLElement).getByText(/最忙一天交通 40 分钟/),
  ).toBeVisible();
  expect(
    within(relaxedCard as HTMLElement).getByText(/西湖断桥/),
  ).toBeVisible();
  expect(within(relaxedCard as HTMLElement).getByText(/灵隐寺/)).toBeVisible();
});

test("explains why one location from an either-or choice was not planned", async () => {
  const user = userEvent.setup();
  const api = fakeApi();
  const basePreflight = await api.preflightV6(SESSION_ID, 1);
  const baseOption = basePreflight.options[0];
  const oneLocationDays = baseOption.days.map((day) => ({
    ...day,
    stops: [baseOption.days[0].stops[0]],
  }));
  vi.mocked(api.preflightV6).mockResolvedValue({
    ...basePreflight,
    options: [{ ...baseOption, days: oneLocationDays }],
  });
  const baseResult = await api.createPlanV6({
    client_request_id: "70000000-0000-4000-8000-000000000008",
    session_id: SESSION_ID,
    selection_revision: 1,
    feasibility_set_id: "70000000-0000-4000-8000-000000000012",
    option_id: baseOption.option_id,
    trip: session().trip,
    selection: {
      accommodation: {
        mode: "exact_poi",
        label: lodging.name,
        confidence: "exact",
        semantic_location_id: LODGING_ID,
        route_anchor_location_id: LODGING_ID,
      },
      pois: [],
      allow_system_recommendations: false,
    },
  });
  vi.mocked(api.createPlanV6).mockResolvedValue({
    ...baseResult,
    plan: baseResult.plan
      ? {
          ...baseResult.plan,
          days: baseResult.plan.days.map((day) => ({
            ...day,
            stops: [baseResult.plan?.days[0].stops[0]].filter(
              (stop): stop is NonNullable<typeof stop> => Boolean(stop),
            ),
          })),
        }
      : null,
  });
  renderPlanner(api);
  await reachTripDetails(user);
  await user.click(screen.getByRole("radio", { name: /与另一地点二选一/ }));
  await user.click(screen.getByRole("checkbox", { name: "西湖断桥" }));
  await user.click(screen.getByRole("checkbox", { name: "灵隐寺" }));
  await user.click(screen.getByRole("button", { name: "应用这个关系" }));
  await user.click(
    screen.getByRole("button", { name: "保存信息并进入空间预检" }),
  );
  await user.click(screen.getByRole("button", { name: "运行空间预检" }));
  await user.click(screen.getByRole("button", { name: "确认方案并生成行程" }));

  const summary = await screen.findByLabelText("选点与安排摘要");
  expect(summary).toHaveTextContent("已选择地点2实际安排地点1未采用地点1");
  expect(summary).toHaveTextContent("灵隐寺：二选一未采用，同行地点已进入计划");
});

async function reachTripDetails(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "查看地图与地点" }));
  await user.click(screen.getByRole("button", { name: "选择住宿" }));
  await user.click(screen.getAllByRole("button", { name: "搜索" })[0]);
  await user.click(
    await screen.findByRole("button", { name: /龙翔桥住宿锚点/ }),
  );
  await user.click(screen.getAllByRole("button", { name: "搜索" })[1]);
  await user.click(await screen.findByRole("button", { name: /西湖断桥/ }));
  await user.click(screen.getByRole("button", { name: /灵隐寺/ }));
  await user.click(
    screen.getByRole("button", { name: "已选好，补充旅行信息" }),
  );
}

function renderPlanner(api: F009Api) {
  render(
    <App
      f009Api={api}
      f009MapLoader={() => Promise.reject(new Error("synthetic map disabled"))}
      createClientRequestId={() => "70000000-0000-4000-8000-000000000008"}
    />,
  );
}

test("keeps the updateTrip revision after updateSelection fails", async () => {
  const user = userEvent.setup();
  const api = fakeApi();
  vi.mocked(api.updateSelection)
    .mockRejectedValueOnce(new F009ClientError("selection_invalid", "invalid"))
    .mockImplementationOnce(async (_sessionId, _revision, nextSelection) => ({
      ...session(nextSelection),
      revision: 2,
    }));
  renderPlanner(api);
  await reachTripDetails(user);

  await user.click(
    screen.getByRole("button", { name: "保存信息并进入空间预检" }),
  );
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "地点关系或住宿信息未通过校验",
  );
  await user.click(
    screen.getByRole("button", { name: "保存信息并进入空间预检" }),
  );

  await waitFor(() => expect(api.updateTrip).toHaveBeenCalledTimes(2));
  expect(vi.mocked(api.updateTrip).mock.calls.map((call) => call[1])).toEqual([
    0, 1,
  ]);
});

test("reads the latest session once and safely continues an owned partial save", async () => {
  const user = userEvent.setup();
  const api = fakeApi() as F009Api & {
    getSession: ReturnType<typeof vi.fn>;
  };
  let desiredTrip: PreplanningSessionDto["trip"] | undefined;
  vi.mocked(api.updateTrip).mockImplementation(
    async (_id, _revision, nextTrip) => {
      desiredTrip = nextTrip;
      throw new F009ClientError(
        "selection_revision_conflict",
        "The preplanning selection has changed.",
      );
    },
  );
  api.getSession = vi.fn(async () => ({
    ...session(),
    revision: 4,
    trip: desiredTrip as PreplanningSessionDto["trip"],
  }));
  renderPlanner(api);
  await reachTripDetails(user);

  await user.click(
    screen.getByRole("button", { name: "保存信息并进入空间预检" }),
  );

  expect(
    await screen.findByRole("heading", { name: "生成前空间预检" }),
  ).toBeInTheDocument();
  expect(api.getSession).toHaveBeenCalledTimes(1);
  expect(api.updateSelection).toHaveBeenCalledTimes(1);
  expect(vi.mocked(api.updateSelection).mock.calls[0][1]).toBe(4);
  expect(
    screen.queryByText(/selection_revision_conflict/),
  ).not.toBeInTheDocument();
});

test("does not overwrite a different latest selection", async () => {
  const user = userEvent.setup();
  const api = fakeApi() as F009Api & {
    getSession: ReturnType<typeof vi.fn>;
  };
  let desiredTrip: PreplanningSessionDto["trip"] | undefined;
  vi.mocked(api.updateTrip).mockImplementation(
    async (_id, _revision, nextTrip) => {
      desiredTrip = nextTrip;
      throw new F009ClientError(
        "selection_revision_conflict",
        "The preplanning selection has changed.",
      );
    },
  );
  api.getSession = vi.fn(async () => ({
    ...session({
      accommodation: {
        mode: "exact_poi",
        label: "另一家酒店",
        confidence: "exact",
        semantic_location_id: LODGING_ID,
        route_anchor_location_id: LODGING_ID,
      },
      pois: [],
      allow_system_recommendations: false,
    }),
    revision: 4,
    trip: desiredTrip as PreplanningSessionDto["trip"],
  }));
  renderPlanner(api);
  await reachTripDetails(user);

  await user.click(
    screen.getByRole("button", { name: "保存信息并进入空间预检" }),
  );

  expect(await screen.findByRole("alert")).toHaveTextContent(
    "规划信息已发生变化，请确认最新选择后重新保存",
  );
  expect(api.getSession).toHaveBeenCalledTimes(1);
  expect(api.updateSelection).not.toHaveBeenCalled();
});

test("shows local saving feedback and blocks rapid duplicate submissions", async () => {
  const user = userEvent.setup();
  const api = fakeApi();
  let finish: ((value: PreplanningSessionDto) => void) | undefined;
  vi.mocked(api.updateTrip).mockImplementation(
    async () =>
      new Promise<PreplanningSessionDto>((resolve) => {
        finish = resolve;
      }),
  );
  renderPlanner(api);
  await reachTripDetails(user);
  const button = screen.getByRole("button", {
    name: "保存信息并进入空间预检",
  });

  fireEvent.click(button);
  fireEvent.click(button);

  expect(await screen.findByText("正在保存旅行信息…")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "正在保存…" })).toBeDisabled();
  expect(api.updateTrip).toHaveBeenCalledTimes(1);
  finish?.({ ...session(), revision: 1 });
});
