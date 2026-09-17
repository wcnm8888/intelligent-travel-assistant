import {
  FormEvent,
  useCallback,
  useEffect,
  useMemo,
  useReducer,
  useRef,
  useState,
} from "react";

import {
  createF009Api,
  F009ClientError,
  type AccommodationChoiceDto,
  type AdvisorSnapshotDto,
  type AdvisorSuggestionDto,
  type F009Api,
  type MapPlanDto,
  type PoiIntentDto,
  type PoiOptionDto,
  type PlanOptionV6Dto,
  type PreflightV6Dto,
  type PreplanningSelectionDto,
  type PreplanningSessionDto,
  type PreplanningTripDto,
  type TripPlanAgentResponseDto,
} from "./f009Api";
import { F009Map } from "./F009Map";
import { F019SelectionView } from "./F019SelectionView";
import { F019Advisor } from "./F019Advisor";
import "./f019-journey.css";
import {
  visitCollectionReducer,
  type MapFocusRequest,
} from "./f019Presentation";
import type { F009MapLoader } from "./f009MapLoader";

interface F009PlannerProps {
  api?: F009Api;
  createClientRequestId?: () => string;
  mapLoader?: F009MapLoader;
  syntheticSelectionMap?: boolean;
}

export function F009Planner({
  api = createF009Api(),
  createClientRequestId = () => crypto.randomUUID(),
  mapLoader,
  syntheticSelectionMap = false,
}: F009PlannerProps) {
  const [step, setStep] = useState<
    "destination" | "selection" | "details" | "preflight" | "result"
  >("destination");
  const [trip, setTrip] = useState(defaultTrip);
  const [session, setSession] = useState<PreplanningSessionDto | null>(null);
  const [accommodationQuery, setAccommodationQuery] = useState("湖滨 龙翔桥");
  const [visitQuery, setVisitQuery] = useState("西湖");
  const [accommodations, setAccommodations] = useState<PoiOptionDto[]>([]);
  const [visitCollection, setVisits] = useReducer(visitCollectionReducer, {
    visible: [],
    catalog: [],
  });
  const visits = visitCollection.visible;
  const displayIndices = useMemo(
    () =>
      new Map(
        visitCollection.catalog.map((option, index) => [
          option.location_id,
          index + 1,
        ]),
      ),
    [visitCollection.catalog],
  );
  const [mapFocus, setMapFocus] = useState<MapFocusRequest | null>(null);
  const [listFocus, setListFocus] = useState<MapFocusRequest | null>(null);
  const operationInFlight = useRef(false);
  const [accommodationId, setAccommodationId] = useState<string | null>(null);
  const [accommodationMode, setAccommodationMode] =
    useState<AccommodationChoiceDto["mode"]>("exact_poi");
  const [pin, setPin] = useState({
    longitude: "120.1600",
    latitude: "30.2500",
  });
  const [pinChoice, setPinChoice] = useState<{
    location_id: string;
    label: string;
  } | null>(null);
  const [intents, setIntents] = useState<PoiIntentDto[]>([]);
  const [pendingSemantic, setPendingSemantic] = useState<PoiOptionDto | null>(
    null,
  );
  const [anchorOptions, setAnchorOptions] = useState<PoiOptionDto[]>([]);
  const [pendingAdvisorSuggestion, setPendingAdvisorSuggestion] =
    useState<AdvisorSuggestionDto | null>(null);
  const [advisorFeedback, setAdvisorFeedback] = useState<{
    kind: "status" | "error";
    message: string;
  } | null>(null);
  const [pendingAdvisorAction, setPendingAdvisorAction] = useState<
    string | null
  >(null);
  const [anchorSearchState, setAnchorSearchState] = useState<
    "searching" | "ready" | "empty" | null
  >(null);
  const [recommendations, setRecommendations] = useState(false);
  const [preflight, setPreflight] = useState<PreflightV6Dto | null>(null);
  const [selectedPlanOptionId, setSelectedPlanOptionId] = useState<
    string | null
  >(null);
  const [plan, setPlan] = useState<TripPlanAgentResponseDto | null>(null);
  const [mapPlan, setMapPlan] = useState<MapPlanDto | null>(null);
  const [advisor, setAdvisor] = useState<AdvisorSnapshotDto | null>(null);
  const [advisorMessage, setAdvisorMessage] = useState("");
  const [advisorOpen, setAdvisorOpen] = useState(true);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveFeedback, setSaveFeedback] = useState<{
    kind: "status" | "error";
    message: string;
    technicalCode?: string;
  } | null>(null);
  const saveInFlight = useRef(false);
  const saveFeedbackRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    document.querySelector<HTMLElement>("[data-f010-step-heading]")?.focus();
  }, [step]);

  const selectedIds = useMemo(
    () =>
      new Set([
        ...(accommodationId ? [accommodationId] : []),
        ...intents.map((intent) => intent.location_id),
      ]),
    [accommodationId, intents],
  );
  const allOptions = useMemo(
    () =>
      uniqueOptions([
        ...accommodations,
        ...visits,
        ...visitCollection.catalog.filter((option) =>
          selectedIds.has(option.location_id),
        ),
      ]),
    [accommodations, visits, visitCollection.catalog, selectedIds],
  );
  const visibleVisitOptions = useMemo(
    () =>
      pendingSemantic
        ? anchorOptions.filter(
            (option) =>
              option.scope_kind === "point" &&
              option.confirmation_status === "verified" &&
              option.location_id !== pendingSemantic.location_id,
          )
        : visits,
    [pendingSemantic, visits, anchorOptions],
  );
  const optionRoles = useMemo(
    () =>
      new Map<string, "accommodation" | "visit">([
        ...visits.map((option) => [option.location_id, "visit"] as const),
        ...accommodations.map(
          (option) => [option.location_id, "accommodation"] as const,
        ),
      ]),
    [accommodations, visits],
  );
  const run = useCallback(
    async (
      operation: () => Promise<void>,
      onFailure?: (message: string) => void,
    ) => {
      if (operationInFlight.current) return;
      operationInFlight.current = true;
      setBusy(true);
      setNotice(null);
      try {
        await operation();
      } catch (error) {
        if (onFailure) onFailure(userFacingError(error));
        else setNotice(userFacingError(error));
      } finally {
        operationInFlight.current = false;
        setBusy(false);
      }
    },
    [],
  );
  const mapSelect = useCallback(
    (locationId: string) => {
      if (step === "selection") {
        setListFocus((current) => ({
          locationId,
          sequence: (current?.sequence ?? 0) + 1,
        }));
        return;
      }
      const cards = document.querySelectorAll<HTMLElement>(
        ".f019-locations [data-location-id], .f009-option-list [data-location-id]",
      );
      Array.from(cards)
        .find((card) => card.dataset.locationId === locationId)
        ?.focus();
    },
    [step],
  );
  const focusMap = (locationId: string) =>
    setMapFocus((current) => ({
      locationId,
      sequence: (current?.sequence ?? 0) + 1,
    }));
  const searchMapArea = useCallback(
    (center: { longitude: number; latitude: number }) => {
      if (!session) return;
      void run(async () => {
        const result = await api.searchPois(
          session.session_id,
          "visit",
          visitQuery,
          { center, radius_m: 5_000 },
        );
        setVisits(result.items);
        setSession((current) =>
          current
            ? { ...current, state: result.state, calls: result.calls }
            : current,
        );
      });
    },
    [api, run, session, visitQuery],
  );

  const createSession = (event: FormEvent) => {
    event.preventDefault();
    void run(async () => {
      const created = await api.createSession(trip);
      setSession(created);
      setVisits({ reset: true });
      setAccommodations([]);
      setAccommodationId(null);
      setIntents([]);
      setMapFocus(null);
      setPreflight(null);
      setPlan(null);
      setMapPlan(null);
      setStep("selection");
      if (api.getAdvisor) setAdvisor(await api.getAdvisor(created.session_id));
    });
  };

  const search = (
    purpose: "visit" | "accommodation",
    overrideQuery?: string,
  ) => {
    if (!session) return;
    const keywords =
      overrideQuery ?? (purpose === "visit" ? visitQuery : accommodationQuery);
    void run(async () => {
      const result = await api.searchPois(
        session.session_id,
        purpose,
        keywords,
      );
      if (purpose === "visit") {
        setVisits((current) =>
          pendingSemantic
            ? uniqueOptions([...current, pendingSemantic, ...result.items])
            : result.items,
        );
        if (pendingSemantic) {
          setAnchorOptions(
            result.items.filter(
              (item) =>
                item.scope_kind === "point" &&
                item.confirmation_status === "verified",
            ),
          );
          setAnchorSearchState(
            result.items.some(
              (item) =>
                item.scope_kind === "point" &&
                item.confirmation_status === "verified",
            )
              ? "ready"
              : "empty",
          );
        }
      } else setAccommodations(result.items);
      setSession((current) =>
        current
          ? { ...current, state: result.state, calls: result.calls }
          : current,
      );
    });
  };

  const chooseVisit = (option: PoiOptionDto) => {
    if (operationInFlight.current) return;
    if (intents.length >= 8) {
      setNotice("最多选择 8 个景点。请先移除一个，再加入新地点。");
      return;
    }
    if (
      !pendingSemantic &&
      intents.some((item) => item.location_id === option.location_id)
    )
      return;
    if (option.confirmation_status === "representative_required") {
      const keywords = `${option.name} 入口`;
      setPendingSemantic(option);
      setAnchorOptions([]);
      setAnchorSearchState("searching");
      setVisitQuery(keywords);
      if (!session) return;
      void run(async () => {
        try {
          const result = await api.searchPois(
            session.session_id,
            "visit",
            keywords,
          );
          const eligible = result.items.filter(
            (item) =>
              item.scope_kind === "point" &&
              item.confirmation_status === "verified",
          );
          setAnchorOptions(eligible);
          setVisits((current) =>
            uniqueOptions([...current, option, ...result.items]),
          );
          setSession((current) =>
            current
              ? { ...current, state: result.state, calls: result.calls }
              : current,
          );
          setAnchorSearchState(eligible.length > 0 ? "ready" : "empty");
        } catch (error) {
          setAnchorSearchState("empty");
          throw error;
        }
      });
      return;
    }
    if (
      pendingSemantic &&
      !anchorOptions.some(
        (item) =>
          item.location_id === option.location_id &&
          item.scope_kind === "point" &&
          item.confirmation_status === "verified",
      )
    )
      return;
    const semantic = pendingSemantic ?? option;
    const newIntent: PoiIntentDto = {
      location_id: semantic.location_id,
      route_anchor_location_id: option.location_id,
      importance: "must_visit",
      either_or_group_id: null,
      visit_group_id: null,
      preferred_day: null,
      expected_duration_minutes: 90,
      omission_allowed: false,
      source: "user_selected",
    };
    if (pendingAdvisorSuggestion) {
      applyAdvisorSuggestion(pendingAdvisorSuggestion, "accept", [
        ...intents,
        newIntent,
      ]);
      return;
    }
    setIntents((current) =>
      current.length >= 8 ||
      current.some((item) => item.location_id === semantic.location_id)
        ? current
        : [...current, newIntent],
    );
    setPendingSemantic(null);
    setAnchorSearchState(null);
    setAnchorOptions([]);
    setNotice(null);
  };

  const cancelAnchorSelection = () => {
    setPendingSemantic(null);
    setAnchorSearchState(null);
    setAnchorOptions([]);
    setPendingAdvisorSuggestion(null);
    setAdvisorFeedback(null);
    setNotice(null);
  };

  const createPin = () => {
    if (!session) return;
    void run(async () => {
      const result = await api.createMapPin(
        session.session_id,
        session.revision,
        {
          longitude: Number(pin.longitude),
          latitude: Number(pin.latitude),
        },
      );
      setPinChoice({ location_id: result.location_id, label: result.label });
      setAccommodationMode("map_pin");
    });
  };

  const currentSelection = (): PreplanningSelectionDto | null => {
    if (!session || intents.length === 0) return null;
    const accommodation = accommodationChoice(
      accommodationMode,
      accommodations,
      accommodationId,
      pinChoice,
      accommodationQuery,
    );
    if (!accommodation) {
      setNotice("请先从列表确认住宿锚点，或完成地图锚点的后端地址确认。");
      return null;
    }
    return {
      accommodation,
      pois: intents,
      allow_system_recommendations: recommendations,
    };
  };

  const continueToDetails = () => {
    if (!currentSelection()) return;
    setNotice(null);
    setStep("details");
  };

  const sendAdvisorTurn = () => {
    if (
      !session ||
      !api.advisorTurn ||
      !advisorMessage.trim() ||
      advisorMessage.length > 500
    )
      return;
    const outgoingMessage = advisorMessage.trim();
    void run(async () => {
      if (advisorRecommendationRequested(outgoingMessage)) {
        const discovered = await api.searchPois(
          session.session_id,
          "visit",
          advisorDiscoveryKeywords(outgoingMessage),
        );
        setVisits((current) =>
          uniqueOptions([...current, ...discovered.items]),
        );
        setSession((current) =>
          current
            ? {
                ...current,
                state: discovered.state,
                calls: discovered.calls,
              }
            : current,
        );
      }
      setAdvisor(
        (await api.advisorTurn?.(
          session.session_id,
          session.revision,
          createClientRequestId(),
          outgoingMessage,
        )) ?? null,
      );
      setAdvisorMessage("");
    });
  };

  const applyAdvisorSuggestion = (
    suggestion: AdvisorSuggestionDto,
    action: "accept" | "ignore",
    confirmedIntents?: PoiIntentDto[],
  ) => {
    if (!session || !api.advisorAction || operationInFlight.current) return;
    setAdvisorFeedback(null);
    const selectionContext =
      suggestion.kind === "poi" && action === "accept"
        ? selectionForAdvisorSuggestion(suggestion, confirmedIntents)
        : null;
    if (suggestion.kind === "poi" && action === "accept" && !selectionContext)
      return;
    const option = visitCollection.catalog.find(
      (item) => item.location_id === suggestion.location_id,
    );
    if (
      action === "accept" &&
      suggestion.kind === "poi" &&
      !confirmedIntents &&
      !intents.some((item) => item.location_id === suggestion.location_id) &&
      option?.confirmation_status === "representative_required"
    ) {
      setPendingAdvisorSuggestion(suggestion);
      chooseVisit(option);
      setAdvisorFeedback({
        kind: "status",
        message: `请先在左侧为“${option.name}”确认具体入口，再完成加入。`,
      });
      return;
    }
    setPendingAdvisorAction(suggestion.suggestion_id);
    void run(
      async () => {
        try {
          const updatedAdvisor = await api.advisorAction?.(
            session.session_id,
            session.revision,
            createClientRequestId(),
            suggestion.suggestion_id,
            action,
            selectionContext,
          );
          if (updatedAdvisor) setAdvisor(updatedAdvisor);
          if (action === "accept") {
            const latest = await api.getSession(session.session_id);
            if (suggestion.kind === "poi") syncLatestSession(latest);
            else {
              setSession(latest);
              setTrip(latest.trip);
            }
            setPreflight(null);
            setMapPlan(null);
          }
          if (
            pendingAdvisorSuggestion?.suggestion_id === suggestion.suggestion_id
          )
            cancelAnchorSelection();
          setAdvisorFeedback({
            kind: "status",
            message:
              action === "ignore"
                ? "已忽略这条建议，已选地点保持不变。"
                : suggestion.kind === "poi"
                  ? `已加入：${suggestion.location_name || suggestion.title}。`
                  : "偏好已确认，已选地点保持不变。",
          });
        } finally {
          setPendingAdvisorAction(null);
        }
      },
      (message) => setAdvisorFeedback({ kind: "error", message }),
    );
  };

  const selectionForAdvisorSuggestion = (
    suggestion: AdvisorSuggestionDto,
    confirmedIntents?: PoiIntentDto[],
  ): PreplanningSelectionDto | null => {
    if (!session || !suggestion.location_id) return null;
    const accommodation = accommodationChoice(
      accommodationMode,
      accommodations,
      accommodationId,
      pinChoice,
      accommodationQuery,
    );
    if (!accommodation) {
      setAdvisorFeedback({
        kind: "error",
        message: "景点建议已保留；请先确认住宿位置，再把它加入行程。",
      });
      return null;
    }
    if (
      !confirmedIntents &&
      intents.length >= 8 &&
      !intents.some((item) => item.location_id === suggestion.location_id)
    ) {
      setAdvisorFeedback({
        kind: "error",
        message: "最多选择 8 个景点。请先移除一个，再加入新地点。",
      });
      return null;
    }
    const pois =
      confirmedIntents ??
      (intents.some((intent) => intent.location_id === suggestion.location_id)
        ? intents
        : [
            ...intents,
            {
              location_id: suggestion.location_id,
              route_anchor_location_id: suggestion.location_id,
              importance: "must_visit" as const,
              either_or_group_id: null,
              visit_group_id: null,
              preferred_day: null,
              expected_duration_minutes: 90,
              omission_allowed: false,
              source: "user_selected" as const,
            },
          ]);
    return {
      accommodation,
      pois,
      allow_system_recommendations: recommendations,
    };
  };

  const saveDetails = () => {
    if (!session || saveInFlight.current) return;
    const selection = currentSelection();
    if (!selection) {
      showSaveFeedback("请先确认住宿和至少一个想去的地点。", "error");
      return;
    }
    const validationError = validateSaveInput(trip, selection);
    if (validationError) {
      showSaveFeedback(validationError, "error");
      return;
    }

    saveInFlight.current = true;
    setBusy(true);
    setSaving(true);
    setNotice(null);
    setSaveFeedback({ kind: "status", message: "正在保存旅行信息…" });
    void (async () => {
      let latest = session;
      let recoveryReadUsed = false;
      const readLatest = async () => {
        if (recoveryReadUsed) {
          throw new F009ClientError(
            "selection_revision_conflict",
            "revision conflict repeated",
          );
        }
        recoveryReadUsed = true;
        const recovered = await api.getSession(session.session_id);
        setSession(recovered);
        return recovered;
      };
      const complete = (updated: PreplanningSessionDto) => {
        setSession(updated);
        setPreflight(null);
        setPlan(null);
        setMapPlan(null);
        setSaveFeedback(null);
        setStep("preflight");
      };
      const ensureSafeRecovery = (recovered: PreplanningSessionDto) => {
        if (!sameValue(recovered.trip, trip)) {
          syncLatestSession(recovered);
          throw new SaveConflictError();
        }
        if (
          recovered.selection !== null &&
          !sameValue(recovered.selection, selection)
        ) {
          syncLatestSession(recovered);
          throw new SaveConflictError();
        }
      };
      const persistSelection = async (base: PreplanningSessionDto) => {
        if (sameValue(base.selection, selection)) return base;
        return api.updateSelection(base.session_id, base.revision, selection);
      };

      try {
        try {
          latest = await api.updateTrip(
            session.session_id,
            session.revision,
            trip,
          );
          setSession(latest);
        } catch (error) {
          if (!isRevisionConflict(error)) throw error;
          latest = await readLatest();
          ensureSafeRecovery(latest);
          setSaveFeedback({
            kind: "status",
            message: "信息已同步，正在继续保存。",
          });
        }

        try {
          complete(await persistSelection(latest));
        } catch (error) {
          if (!isRevisionConflict(error)) throw error;
          latest = await readLatest();
          ensureSafeRecovery(latest);
          setSaveFeedback({
            kind: "status",
            message: "信息已同步，正在继续保存。",
          });
          complete(await persistSelection(latest));
        }
      } catch (error) {
        const conflict = error instanceof SaveConflictError;
        showSaveFeedback(
          conflict
            ? "规划信息已发生变化，请确认最新选择后重新保存。"
            : saveErrorMessage(error),
          "error",
          conflict ? "selection_revision_conflict" : safeErrorCode(error),
        );
      } finally {
        saveInFlight.current = false;
        setSaving(false);
        setBusy(false);
      }
    })();
  };

  const showSaveFeedback = (
    message: string,
    kind: "status" | "error",
    technicalCode?: string,
  ) => {
    setSaveFeedback({ kind, message, technicalCode });
    if (kind === "error") {
      window.setTimeout(() => saveFeedbackRef.current?.focus(), 0);
    }
  };

  const syncLatestSession = (latest: PreplanningSessionDto) => {
    setSession(latest);
    setTrip(latest.trip);
    if (!latest.selection) return;
    const latestSelection = latest.selection;
    setAccommodationMode(latestSelection.accommodation.mode);
    setAccommodationId(
      latestSelection.accommodation.semantic_location_id ??
        latestSelection.accommodation.route_anchor_location_id,
    );
    setPinChoice(
      latestSelection.accommodation.mode === "map_pin"
        ? {
            location_id: latestSelection.accommodation.route_anchor_location_id,
            label: latestSelection.accommodation.label,
          }
        : null,
    );
    setIntents(latestSelection.pois);
    setRecommendations(latestSelection.allow_system_recommendations);
  };

  const runPreflight = () => {
    if (!session?.selection) return;
    void run(async () => {
      const result = await api.preflightV6(
        session.session_id,
        session.revision,
      );
      setPreflight(result);
      setSelectedPlanOptionId(result.options[0]?.option_id ?? null);
      setSession({ ...session, state: result.state, calls: result.calls });
    });
  };

  const createPlan = () => {
    if (
      !session?.selection ||
      !preflight?.feasibility_set_id ||
      !selectedPlanOptionId
    )
      return;
    const feasibilitySetId = preflight.feasibility_set_id;
    const optionId = selectedPlanOptionId;
    void run(async () => {
      const created = await api.createPlanV6({
        client_request_id: createClientRequestId(),
        session_id: session.session_id,
        selection_revision: session.revision,
        feasibility_set_id: feasibilitySetId,
        option_id: optionId,
        trip: session.trip,
        selection: session.selection as PreplanningSelectionDto,
      });
      setPlan(created);
      setStep("result");
      try {
        setMapPlan(await api.readMap(created.job_id));
      } catch {
        setMapPlan(null);
        setNotice("地图路线暂不可用，确定性计划与完整列表已保留。");
      }
    });
  };

  const applyRecovery = (
    input: Parameters<F009Api["applyRecoveryAction"]>[3],
  ) => {
    if (!session) return;
    void run(async () => {
      const latest = await api.applyRecoveryAction(
        session.session_id,
        session.revision,
        createClientRequestId(),
        input,
      );
      syncLatestSession(latest);
      setPreflight(null);
      setSelectedPlanOptionId(null);
      setNotice("已按你的确认更新选择，请重新运行空间预检。");
    });
  };

  const retryNarrative = () => {
    if (!plan) return;
    void run(async () => {
      setPlan(
        await api.retryNarrative(
          plan.job_id,
          createClientRequestId(),
          plan.response_version,
        ),
      );
    });
  };

  return (
    <section
      className="f009-planner f019-journey"
      data-journey-step={step}
      aria-labelledby={
        step === "selection" && session ? "f019-title" : "f019-journey-title"
      }
    >
      {step !== "selection" && (
        <>
          <header className="f019-journey-header">
            <div className="f019-brand">
              <span className="f019-brand-mark">行</span>
              <strong>行旅</strong>
              <small>旅行顾问</small>
            </div>
            <nav aria-label="旅行进度" className="f019-journey-steps">
              <span aria-current={step === "destination" ? "step" : undefined}>
                01 旅行需求
              </span>
              <span>02 选地点</span>
              <span aria-current={step !== "destination" ? "step" : undefined}>
                03 比较方案
              </span>
            </nav>
            <span className="f019-journey-city">
              {session ? trip.city : "开始你的旅行"}
            </span>
          </header>
          <div className="f019-journey-context">
            <h2 id="f019-journey-title" tabIndex={-1}>
              {
                {
                  destination: "从想去的地方开始",
                  details: "把旅行安排得更合适",
                  preflight: "看看哪些安排可行",
                  result: "你的旅行，已整理就绪",
                }[step]
              }
            </h2>
            <p>
              {
                {
                  destination: "先选目的地，再一起挑选想去的地点。",
                  details: "保留已选地点，补充日期、预算与出行方式。",
                  preflight: "先核验安排，再确认适合你的方案。",
                  result: "查看每日安排与说明，也可以返回调整选择。",
                }[step]
              }
            </p>
          </div>
        </>
      )}
      <header className="f009-heading">
        <div>
          <p className="section-kicker">V6 · TRAVEL ADVISOR JOURNEY</p>
          <h2 id="f009-title">先决定去哪里，再形成一份可行计划</h2>
        </div>
        <span>地图辅助发现 · 列表始终可操作</span>
      </header>

      <nav className="f010-steps" aria-label="规划进度">
        {[
          ["destination", "01", "目的地"],
          ["selection", "02", "地图选点"],
          ["details", "03", "旅行信息"],
          ["preflight", "04", "空间预检"],
          ["result", "05", "计划结果"],
        ].map(([key, number, label]) => (
          <span
            key={key}
            aria-current={step === key ? "step" : undefined}
            data-active={step === key}
            data-complete={stepRank(step) > stepRank(key)}
          >
            <b>{number}</b>
            {label}
          </span>
        ))}
      </nav>

      {notice && step !== "selection" && (
        <p className="form-notice" role="alert">
          {notice}
        </p>
      )}

      {step === "destination" || !session ? (
        <div className="f009-grid">
          <div className="f009-controls">
            <DestinationForm
              trip={trip}
              disabled={busy}
              onChange={setTrip}
              onSubmit={createSession}
            />
            <section className="f009-action-card" aria-label="正式地点列表">
              <h3>正式地点列表</h3>
              <p className="f009-muted">
                确认城市后，可在此搜索住宿锚点和想去的地点。地图不可用时，这个列表仍可完成全部流程。
              </p>
            </section>
          </div>
          <div className="f009-visuals">
            <F009Map
              options={[]}
              optionRoles={new Map()}
              selectedLocationIds={new Set()}
              mapPlan={null}
              onSelect={() => undefined}
              loader={mapLoader}
            />
          </div>
        </div>
      ) : step === "selection" ? (
        <F019SelectionView
          city={trip.city}
          accommodation={
            accommodationMode === "map_pin" && pinChoice
              ? { location_id: pinChoice.location_id, name: pinChoice.label }
              : (accommodations.find(
                  (option) => option.location_id === accommodationId,
                ) ?? null)
          }
          visits={allOptions.filter((option) => option.purpose === "visit")}
          indices={displayIndices}
          selected={selectedIds}
          selectedCount={intents.length}
          pendingCount={advisor?.pending_suggestions.length ?? 0}
          busy={busy}
          notice={notice}
          listFocus={listFocus}
          anchorPending={!!pendingSemantic}
          onChoose={chooseVisit}
          onRemove={(locationId) => {
            if (operationInFlight.current) return;
            setIntents((current) =>
              current
                .filter((intent) => intent.location_id !== locationId)
                .map((intent, _, remaining) => ({
                  ...intent,
                  either_or_group_id:
                    intent.either_or_group_id &&
                    remaining.filter(
                      (item) =>
                        item.either_or_group_id === intent.either_or_group_id,
                    ).length >= 2
                      ? intent.either_or_group_id
                      : null,
                  visit_group_id:
                    intent.visit_group_id &&
                    remaining.filter(
                      (item) => item.visit_group_id === intent.visit_group_id,
                    ).length >= 2
                      ? intent.visit_group_id
                      : null,
                })),
            );
            setNotice(null);
          }}
          anchorTask={
            pendingSemantic ? (
              <section
                className="f020-anchor-task"
                aria-label="确认景区入口"
                tabIndex={-1}
              >
                <h3>为“{pendingSemantic.name}”确认具体入口</h3>
                <p>
                  {anchorSearchState === "searching"
                    ? "正在查找入口或子景点…"
                    : "景区范围较大。请明确一个到达位置，地图仍可查看；确认前不会加入已选。"}
                </p>
                <form
                  onSubmit={(event) => {
                    event.preventDefault();
                    search("visit");
                  }}
                >
                  <input
                    aria-label="景区入口搜索"
                    value={visitQuery}
                    onChange={(event) => setVisitQuery(event.target.value)}
                    disabled={busy}
                  />
                  <button
                    className="f019-button f019-secondary"
                    type="submit"
                    disabled={busy}
                  >
                    搜索入口
                  </button>
                </form>
                {anchorSearchState === "empty" && (
                  <p role="status">
                    暂未找到可用入口，请修改关键词或取消选择。
                  </p>
                )}
                {visibleVisitOptions.map((option) => (
                  <article key={option.location_id}>
                    <h4>{option.name}</h4>
                    <button
                      className="f019-button f019-primary"
                      type="button"
                      aria-label={`用作路线入口：${option.name}`}
                      disabled={busy}
                      onClick={() => chooseVisit(option)}
                    >
                      用作路线入口
                    </button>
                    <button
                      className="f019-button f019-ghost"
                      type="button"
                      onClick={() => focusMap(option.location_id)}
                    >
                      地图查看
                    </button>
                  </article>
                ))}
                <button
                  className="f019-button f019-secondary"
                  type="button"
                  onClick={cancelAnchorSelection}
                  disabled={busy}
                >
                  取消选择
                </button>
              </section>
            ) : null
          }
          onView={focusMap}
          onDestination={() => setStep("destination")}
          onContinue={continueToDetails}
          onSearch={(query) => {
            setVisitQuery(query);
            search("visit", query);
          }}
          editor={
            <fieldset
              className="f009-controls f019-editor-controls"
              disabled={busy}
            >
              <h3 className="sr-only" data-f010-step-heading tabIndex={-1}>
                选择住宿与想去的地点
              </h3>
              <SessionStatus session={session} />
              <SearchPanel
                title="你打算住在哪里？"
                query={accommodationQuery}
                onQuery={setAccommodationQuery}
                onSearch={() => search("accommodation")}
                disabled={busy}
              >
                <div
                  className="f009-mode-row"
                  role="radiogroup"
                  aria-label="住宿选择方式"
                >
                  {(["area", "exact_poi", "map_pin"] as const).map((mode) => (
                    <label key={mode}>
                      <input
                        type="radio"
                        name="accommodation-mode"
                        checked={accommodationMode === mode}
                        onChange={() => setAccommodationMode(mode)}
                      />
                      {
                        {
                          area: "大概区域",
                          exact_poi: "已确定酒店",
                          map_pin: "地图上选择",
                        }[mode]
                      }
                    </label>
                  ))}
                </div>
                <p className="f009-muted f011-accommodation-help">
                  大概区域需要从候选中确认一个附近位置用于估算路线；已确定酒店使用核验后的具体住宿；地图上选择会由后端确认地址，只作为每天出发和返回的位置。
                </p>
                {accommodationMode === "map_pin" ? (
                  <div className="f009-pin-fields">
                    <label>
                      经度
                      <input
                        value={pin.longitude}
                        onChange={(e) =>
                          setPin({ ...pin, longitude: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      纬度
                      <input
                        value={pin.latitude}
                        onChange={(e) =>
                          setPin({ ...pin, latitude: e.target.value })
                        }
                      />
                    </label>
                    <button type="button" onClick={createPin} disabled={busy}>
                      确认这个位置
                    </button>
                    {pinChoice && (
                      <p role="status">已确认：{pinChoice.label}</p>
                    )}
                  </div>
                ) : (
                  <OptionList
                    options={accommodations}
                    selected={new Set(accommodationId ? [accommodationId] : [])}
                    actionLabel={
                      accommodationMode === "area"
                        ? "用这个位置估算路线"
                        : "选择这家住宿"
                    }
                    onChoose={(option) => {
                      setAccommodationId(option.location_id);
                      focusMap(option.location_id);
                    }}
                  />
                )}
              </SearchPanel>

              <SearchPanel
                title="想去的地点与关系"
                query={visitQuery}
                onQuery={setVisitQuery}
                onSearch={() => search("visit")}
                disabled={busy}
              >
                {pendingSemantic && (
                  <div className="f018-anchor-task" role="status">
                    <div>
                      <strong>
                        {anchorSearchState === "searching"
                          ? `正在查找“${pendingSemantic.name}”的具体入口…`
                          : `为“${pendingSemantic.name}”选择一个具体入口`}
                      </strong>
                      <p>
                        {anchorSearchState === "empty"
                          ? "暂未找到可用于路线计算的入口或子景点。你可以修改关键词后重试，或取消本次选择。"
                          : "景区范围较大；下方只显示可以作为每天到达点的具体入口或子景点。"}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="secondary-button"
                      onClick={cancelAnchorSelection}
                      disabled={busy}
                    >
                      取消选择
                    </button>
                  </div>
                )}
                <OptionList
                  options={visibleVisitOptions}
                  selected={selectedIds}
                  resolvedRepresentativeIds={
                    new Set(
                      intents
                        .filter(
                          (intent) =>
                            intent.location_id !==
                            intent.route_anchor_location_id,
                        )
                        .map((intent) => intent.location_id),
                    )
                  }
                  actionLabel={pendingSemantic ? "用作路线入口" : "加入行程"}
                  onChoose={chooseVisit}
                />
                <IntentEditor
                  intents={intents}
                  options={allOptions}
                  onChange={setIntents}
                />
                <label className="f009-recommendations">
                  <input
                    type="checkbox"
                    checked={recommendations}
                    onChange={(event) =>
                      setRecommendations(event.target.checked)
                    }
                  />
                  允许系统推荐同城、同类别、5 km 内的可达替代点（默认关闭）
                </label>
                <div className="f010-flow-actions">
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() => setStep("destination")}
                  >
                    修改目的地
                  </button>
                  <button
                    type="button"
                    onClick={continueToDetails}
                    disabled={busy || intents.length === 0}
                  >
                    已选好，补充旅行信息
                  </button>
                </div>
              </SearchPanel>
            </fieldset>
          }
          map={
            <F009Map
              options={allOptions}
              optionRoles={optionRoles}
              selectedLocationIds={selectedIds}
              mapPlan={null}
              onSelect={mapSelect}
              onSearchArea={searchMapArea}
              loader={mapLoader}
              syntheticPresentation={syntheticSelectionMap}
              city={trip.city}
              displayIndices={displayIndices}
              focusRequest={mapFocus}
            />
          }
          advisor={
            advisor ? (
              <F019Advisor
                snapshot={advisor}
                feedback={advisorFeedback}
                pendingActionId={pendingAdvisorAction}
                message={advisorMessage}
                disabled={busy}
                expanded={advisorOpen}
                onToggle={() => setAdvisorOpen((current) => !current)}
                onMessage={setAdvisorMessage}
                onSend={sendAdvisorTurn}
                onAction={applyAdvisorSuggestion}
                onView={focusMap}
                indices={displayIndices}
                selected={selectedIds}
              />
            ) : (
              <aside className="f019-panel">
                旅行顾问暂不可用，仍可在清单选择地点。
              </aside>
            )
          }
        />
      ) : step === "details" ? (
        <TripDetailsForm
          trip={trip}
          disabled={busy}
          saving={saving}
          saveFeedback={saveFeedback}
          saveFeedbackRef={saveFeedbackRef}
          selectedCount={intents.length}
          intents={intents}
          options={allOptions}
          onChange={setTrip}
          onIntentsChange={setIntents}
          onBack={() => setStep("selection")}
          onSubmit={saveDetails}
        />
      ) : step === "preflight" ? (
        <div className="f010-preflight-layout">
          <section
            className="f009-action-card"
            aria-labelledby="preflight-heading"
          >
            <SessionStatus session={session} />
            <p className="section-kicker">SERVER-SIDE FACT CHECK</p>
            <h3 id="preflight-heading" data-f010-step-heading tabIndex={-1}>
              生成前空间预检
            </h3>
            <p className="f009-muted">
              后端将核验身份、路线端点、真实交通时间、每日容量和组关系。DeepSeek
              不参与地点选择或排序。
            </p>
            <div className="f010-flow-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setStep("details")}
              >
                返回修改信息
              </button>
              <button
                type="button"
                onClick={runPreflight}
                disabled={busy || !session.selection}
              >
                运行空间预检
              </button>
            </div>
            {preflight && (
              <V6PreflightResult
                result={preflight}
                intents={intents}
                options={allOptions}
                selectedOptionId={selectedPlanOptionId}
                onSelectOption={setSelectedPlanOptionId}
                onRecovery={applyRecovery}
                dayCount={session.trip.day_windows.length}
              />
            )}
            {preflight?.state === "feasible" && (
              <button
                type="button"
                onClick={createPlan}
                disabled={busy || !selectedPlanOptionId}
              >
                确认方案并生成行程
              </button>
            )}
          </section>
        </div>
      ) : (
        <div
          className="f009-grid f010-result-layout"
          data-map-content={mapPlan ? "available" : "unavailable"}
        >
          <div className="f009-controls">
            <div className="f010-flow-actions">
              <button
                type="button"
                className="secondary-button"
                onClick={() => setStep("selection")}
              >
                返回选点并重新预检
              </button>
            </div>
            {plan && (
              <AgentPlanResult
                result={plan}
                mapPlan={mapPlan}
                intents={intents}
                options={allOptions}
                onRetryNarrative={retryNarrative}
                retrying={busy}
              />
            )}
          </div>
          <div className="f009-visuals">
            <F009Map
              options={allOptions}
              optionRoles={optionRoles}
              selectedLocationIds={selectedIds}
              mapPlan={mapPlan}
              onSelect={mapSelect}
              loader={mapLoader}
            />
          </div>
        </div>
      )}
    </section>
  );
}

function DestinationForm({
  trip,
  disabled,
  onChange,
  onSubmit,
}: {
  trip: PreplanningTripDto;
  disabled: boolean;
  onChange(value: PreplanningTripDto): void;
  onSubmit(event: FormEvent): void;
}) {
  return (
    <form className="f010-destination" onSubmit={onSubmit}>
      <p className="section-kicker">START WITH PLACE</p>
      <h3 data-f010-step-heading tabIndex={-1}>
        这次想去哪个城市？
      </h3>
      <p>先确认目的地并浏览地图与地点列表。日期、预算和偏好会在选点后补充。</p>
      <label>
        目的地城市
        <input
          required
          value={trip.city}
          onChange={(e) => onChange({ ...trip, city: e.target.value })}
        />
      </label>
      <button type="submit" disabled={disabled}>
        查看地图与地点
      </button>
    </form>
  );
}

function TripDetailsForm({
  trip,
  disabled,
  saving,
  saveFeedback,
  saveFeedbackRef,
  selectedCount,
  intents,
  options,
  onChange,
  onIntentsChange,
  onBack,
  onSubmit,
}: {
  trip: PreplanningTripDto;
  disabled: boolean;
  saving: boolean;
  saveFeedback: {
    kind: "status" | "error";
    message: string;
    technicalCode?: string;
  } | null;
  saveFeedbackRef: React.RefObject<HTMLDivElement | null>;
  selectedCount: number;
  intents: PoiIntentDto[];
  options: PoiOptionDto[];
  onChange(value: PreplanningTripDto): void;
  onIntentsChange(value: PoiIntentDto[]): void;
  onBack(): void;
  onSubmit(): void;
}) {
  const toggleMode = (mode: "walking" | "public_transit", checked: boolean) => {
    const modes = checked
      ? [...new Set([...trip.transport_modes, mode])]
      : trip.transport_modes.filter((item) => item !== mode);
    if (modes.length) onChange({ ...trip, transport_modes: modes });
  };
  return (
    <form
      className="f010-details"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <header>
        <p className="section-kicker">TRIP PARAMETERS</p>
        <h3 data-f010-step-heading tabIndex={-1}>
          为已选的 {selectedCount} 个地点补充旅行信息
        </h3>
        <p>这些信息用于容量、时间窗口与路线预检，不会交给模型决定地点。</p>
      </header>
      <div className="f010-details-grid">
        <label>
          开始日期
          <input
            type="date"
            required
            value={trip.start_date}
            onChange={(e) =>
              onChange(withDates(trip, e.target.value, trip.end_date))
            }
          />
        </label>
        <label>
          结束日期
          <input
            type="date"
            required
            value={trip.end_date}
            onChange={(e) =>
              onChange(withDates(trip, trip.start_date, e.target.value))
            }
          />
        </label>
        <label>
          同行人数
          <input
            type="number"
            min="1"
            max="8"
            value={trip.travelers}
            onChange={(e) =>
              onChange({ ...trip, travelers: Number(e.target.value) })
            }
          />
        </label>
        <label>
          总预算（CNY）
          <input
            inputMode="decimal"
            required
            value={trip.total_budget.amount}
            onChange={(e) =>
              onChange({
                ...trip,
                total_budget: { amount: e.target.value, currency: "CNY" },
              })
            }
          />
        </label>
        <label>
          住宿每晚预算（CNY）
          <input
            inputMode="decimal"
            value={trip.one_night_cost?.amount ?? "500"}
            onChange={(e) =>
              onChange({
                ...trip,
                one_night_cost: { amount: e.target.value, currency: "CNY" },
              })
            }
          />
        </label>
        <label>
          每人每日餐饮预算（CNY）
          <input
            inputMode="decimal"
            value={trip.meal_budget_per_person_per_day?.amount ?? "100"}
            onChange={(e) =>
              onChange({
                ...trip,
                meal_budget_per_person_per_day: {
                  amount: e.target.value,
                  currency: "CNY",
                },
              })
            }
          />
        </label>
        <label>
          旅行节奏
          <select
            value={trip.pace}
            onChange={(e) =>
              onChange({
                ...trip,
                pace: e.target.value as PreplanningTripDto["pace"],
              })
            }
          >
            <option value="relaxed">轻松</option>
            <option value="balanced">均衡</option>
            <option value="intensive">紧凑</option>
          </select>
        </label>
        <fieldset>
          <legend>市内交通</legend>
          <label>
            <input
              type="checkbox"
              checked={trip.transport_modes.includes("public_transit")}
              onChange={(e) => toggleMode("public_transit", e.target.checked)}
            />
            公共交通
          </label>
          <label>
            <input
              type="checkbox"
              checked={trip.transport_modes.includes("walking")}
              onChange={(e) => toggleMode("walking", e.target.checked)}
            />
            步行
          </label>
        </fieldset>
        <label className="f010-span">
          兴趣（用逗号分隔）
          <input
            value={trip.preferences.interests.join("，")}
            onChange={(e) =>
              onChange({
                ...trip,
                preferences: {
                  ...trip.preferences,
                  interests: e.target.value
                    .split(/[，,]/)
                    .map((item) => item.trim())
                    .filter(Boolean)
                    .slice(0, 5),
                },
              })
            }
          />
        </label>
        <label className="f010-span">
          补充偏好
          <textarea
            maxLength={200}
            value={trip.preferences.free_text}
            onChange={(e) =>
              onChange({
                ...trip,
                preferences: { ...trip.preferences, free_text: e.target.value },
              })
            }
          />
        </label>
      </div>
      <section
        className="f010-place-constraints"
        aria-labelledby="place-constraints-title"
      >
        <h4 id="place-constraints-title">地点关系、日期偏好与预计时长</h4>
        <RelationshipEditor
          intents={intents}
          options={options}
          onChange={onIntentsChange}
        />
        <IntentEditor
          intents={intents}
          options={options}
          onChange={onIntentsChange}
        />
      </section>
      <div className="f010-flow-actions">
        <button type="button" className="secondary-button" onClick={onBack}>
          返回选点
        </button>
        <button type="submit" disabled={disabled || saving}>
          {saving ? "正在保存…" : "保存信息并进入空间预检"}
        </button>
      </div>
      {(saving || saveFeedback) && (
        <div
          className="f012-save-feedback"
          ref={saveFeedbackRef}
          role={saveFeedback?.kind === "error" ? "alert" : "status"}
          tabIndex={-1}
          data-kind={saveFeedback?.kind ?? "status"}
        >
          <strong>
            {saving
              ? (saveFeedback?.message ?? "正在保存旅行信息…")
              : saveFeedback?.message}
          </strong>
          {saveFeedback?.technicalCode && (
            <details>
              <summary>查看技术详情</summary>
              <code>{saveFeedback.technicalCode}</code>
            </details>
          )}
        </div>
      )}
    </form>
  );
}

function stepRank(step: string): number {
  return ["destination", "selection", "details", "preflight", "result"].indexOf(
    step,
  );
}

function SearchPanel({
  title,
  query,
  onQuery,
  onSearch,
  disabled,
  children,
}: {
  title: string;
  query: string;
  onQuery(value: string): void;
  onSearch(): void;
  disabled: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className="f009-action-card">
      <h3>{title}</h3>
      <div className="f009-search-row">
        <label>
          搜索关键词
          <input
            value={query}
            onChange={(event) => onQuery(event.target.value)}
          />
        </label>
        <button
          type="button"
          onClick={onSearch}
          disabled={disabled || !query.trim()}
        >
          搜索
        </button>
      </div>
      {children}
    </section>
  );
}

function OptionList({
  options,
  selected,
  resolvedRepresentativeIds = new Set<string>(),
  actionLabel,
  onChoose,
}: {
  options: PoiOptionDto[];
  selected: ReadonlySet<string>;
  resolvedRepresentativeIds?: ReadonlySet<string>;
  actionLabel: string;
  onChoose(option: PoiOptionDto): void;
}) {
  if (options.length === 0)
    return <p className="f009-muted">暂无已验证候选。</p>;
  return (
    <ul className="f009-option-list">
      {options.map((option) => (
        <li
          key={option.location_id}
          data-selected={selected.has(option.location_id)}
        >
          <button
            type="button"
            data-location-id={option.location_id}
            onClick={() => onChoose(option)}
          >
            <strong>{option.name}</strong>
            <span>
              {option.category_label} · {option.district_adcode}
            </span>
            <small>{option.address || "地址未提供"}</small>
            <em>
              {resolvedRepresentativeIds.has(option.location_id)
                ? "已选择，路线入口已确认"
                : option.confirmation_status === "representative_required"
                  ? "需具体路线锚点"
                  : actionLabel}
            </em>
          </button>
        </li>
      ))}
    </ul>
  );
}

type RelationshipMode = "independent" | "either_or" | "visit_group";

function RelationshipEditor({
  intents,
  options,
  onChange,
}: {
  intents: PoiIntentDto[];
  options: PoiOptionDto[];
  onChange(value: PoiIntentDto[]): void;
}) {
  const [mode, setMode] = useState<RelationshipMode>("independent");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const names = new Map(
    options.map((option) => [option.location_id, option.name]),
  );
  const minimum = mode === "independent" ? 1 : 2;
  const groups = relationshipGroups(intents);
  const applyRelationship = () => {
    const chosen = intents
      .filter((intent) => selectedIds.includes(intent.location_id))
      .map((intent) => intent.location_id)
      .sort();
    if (chosen.length < minimum) return;
    const chosenSet = new Set(chosen);
    const reference = intents.find((intent) =>
      chosenSet.has(intent.location_id),
    );
    const groupId =
      mode === "independent" ? null : relationshipGroupId(mode, chosen);
    const next = intents.map((intent) => {
      if (!chosenSet.has(intent.location_id)) return intent;
      if (mode === "independent") {
        return {
          ...intent,
          either_or_group_id: null,
          visit_group_id: null,
        };
      }
      const importance = reference?.importance ?? intent.importance;
      return {
        ...intent,
        importance,
        omission_allowed:
          importance === "must_visit" ? false : intent.omission_allowed,
        preferred_day:
          mode === "visit_group"
            ? (reference?.preferred_day ?? null)
            : intent.preferred_day,
        either_or_group_id: mode === "either_or" ? groupId : null,
        visit_group_id: mode === "visit_group" ? groupId : null,
      };
    });
    onChange(normalizeRelationshipGroups(next));
    setSelectedIds([]);
  };

  return (
    <section
      className="f011-relationship-editor"
      aria-labelledby="relationship-title"
    >
      <div className="f011-relationship-heading">
        <div>
          <h5 id="relationship-title">这些地点之间是什么关系？</h5>
          <p>选择关系，再勾选地点。系统会自动保持组合规则，不需要填写编号。</p>
        </div>
        <span>{intents.length} 个已选地点</span>
      </div>
      <fieldset className="f011-relationship-modes">
        <legend>游览关系</legend>
        {(
          [
            ["independent", "独立游览", "各自安排"],
            ["either_or", "与另一地点二选一", "计划只选其中一个"],
            ["visit_group", "与其他地点一起游览", "同一天连续安排"],
          ] as const
        ).map(([value, label, help]) => (
          <label key={value}>
            <input
              type="radio"
              name="place-relationship-mode"
              value={value}
              checked={mode === value}
              onChange={() => {
                setMode(value);
                setSelectedIds([]);
              }}
            />
            <span>
              <strong>{label}</strong>
              <small>{help}</small>
            </span>
          </label>
        ))}
      </fieldset>
      <fieldset className="f011-relationship-places">
        <legend>
          {mode === "independent" ? "选择要解除组合的地点" : "选择至少两个地点"}
        </legend>
        {intents.map((intent) => (
          <label key={intent.location_id}>
            <input
              type="checkbox"
              checked={selectedIds.includes(intent.location_id)}
              onChange={(event) =>
                setSelectedIds((current) =>
                  event.target.checked
                    ? [...current, intent.location_id]
                    : current.filter((id) => id !== intent.location_id),
                )
              }
            />
            <span>{names.get(intent.location_id) ?? "已确认地点"}</span>
          </label>
        ))}
      </fieldset>
      <button
        type="button"
        className="f011-relationship-apply"
        disabled={selectedIds.length < minimum}
        onClick={applyRelationship}
      >
        {mode === "independent" ? "设为独立游览" : "应用这个关系"}
      </button>
      {groups.length > 0 && (
        <ul className="f011-relationship-summary" aria-label="已建立的地点关系">
          {groups.map((group) => (
            <li key={`${group.kind}-${group.id}`}>
              <div>
                <strong>
                  {group.kind === "either_or" ? "二选一" : "一起游览"}
                </strong>
                <span>
                  {group.locationIds
                    .map((id) => names.get(id) ?? "已确认地点")
                    .join(" · ")}
                </span>
              </div>
              <button
                type="button"
                onClick={() =>
                  onChange(
                    intents.map((intent) =>
                      intent.either_or_group_id === group.id ||
                      intent.visit_group_id === group.id
                        ? {
                            ...intent,
                            either_or_group_id: null,
                            visit_group_id: null,
                          }
                        : intent,
                    ),
                  )
                }
              >
                解除关系
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function IntentEditor({
  intents,
  options,
  onChange,
}: {
  intents: PoiIntentDto[];
  options: PoiOptionDto[];
  onChange(value: PoiIntentDto[]): void;
}) {
  const names = new Map(
    options.map((option) => [option.location_id, option.name]),
  );
  const update = (index: number, patch: Partial<PoiIntentDto>) =>
    onChange(updateIntentAndGroup(intents, index, patch));
  return (
    <ol className="f009-intents">
      {intents.map((intent, index) => (
        <li
          key={intent.location_id}
          data-location-id={intent.location_id}
          tabIndex={-1}
        >
          <strong>{names.get(intent.location_id) ?? "已确认语义地点"}</strong>
          <label>
            优先级
            <select
              value={intent.importance}
              onChange={(e) =>
                update(index, {
                  importance: e.target.value as PoiIntentDto["importance"],
                  omission_allowed:
                    e.target.value === "optional"
                      ? intent.omission_allowed
                      : false,
                })
              }
            >
              <option value="must_visit">必去</option>
              <option value="optional">可选</option>
            </select>
          </label>
          <label>
            预计分钟
            <input
              type="number"
              min="30"
              max="480"
              step="15"
              value={intent.expected_duration_minutes ?? 90}
              onChange={(e) =>
                update(index, {
                  expected_duration_minutes: Number(e.target.value),
                })
              }
            />
          </label>
          <label>
            偏好日（1 开始）
            <input
              type="number"
              min="1"
              max="7"
              value={
                intent.preferred_day == null ? "" : intent.preferred_day + 1
              }
              onChange={(e) =>
                update(index, {
                  preferred_day: e.target.value
                    ? Number(e.target.value) - 1
                    : null,
                })
              }
            />
          </label>
          <RelationshipBadge intent={intent} />
          <label>
            <input
              type="checkbox"
              checked={intent.omission_allowed}
              disabled={intent.importance !== "optional"}
              onChange={(e) =>
                update(index, { omission_allowed: e.target.checked })
              }
            />
            允许省略
          </label>
          <button
            type="button"
            onClick={() =>
              onChange(
                normalizeRelationshipGroups(
                  intents.filter((_, current) => current !== index),
                ),
              )
            }
          >
            移除
          </button>
        </li>
      ))}
    </ol>
  );
}

function RelationshipBadge({ intent }: { intent: PoiIntentDto }) {
  const label = intent.either_or_group_id
    ? "二选一安排"
    : intent.visit_group_id
      ? "一起游览"
      : "独立游览";
  return <span className="f011-relationship-badge">{label}</span>;
}

function updateIntentAndGroup(
  intents: PoiIntentDto[],
  index: number,
  patch: Partial<PoiIntentDto>,
): PoiIntentDto[] {
  const target = intents[index];
  const groupId = target.either_or_group_id ?? target.visit_group_id;
  const updatesGroup =
    groupId != null &&
    (patch.importance !== undefined ||
      (target.visit_group_id != null &&
        Object.prototype.hasOwnProperty.call(patch, "preferred_day")));
  return intents.map((intent, current) => {
    if (
      current !== index &&
      (!updatesGroup ||
        (intent.either_or_group_id !== groupId &&
          intent.visit_group_id !== groupId))
    ) {
      return intent;
    }
    const next = { ...intent, ...patch };
    return next.importance === "must_visit"
      ? { ...next, omission_allowed: false }
      : next;
  });
}

function normalizeRelationshipGroups(intents: PoiIntentDto[]): PoiIntentDto[] {
  const eitherCounts = new Map<string, number>();
  const visitCounts = new Map<string, number>();
  for (const intent of intents) {
    if (intent.either_or_group_id) {
      eitherCounts.set(
        intent.either_or_group_id,
        (eitherCounts.get(intent.either_or_group_id) ?? 0) + 1,
      );
    }
    if (intent.visit_group_id) {
      visitCounts.set(
        intent.visit_group_id,
        (visitCounts.get(intent.visit_group_id) ?? 0) + 1,
      );
    }
  }
  return intents.map((intent) => ({
    ...intent,
    either_or_group_id:
      intent.either_or_group_id &&
      (eitherCounts.get(intent.either_or_group_id) ?? 0) >= 2
        ? intent.either_or_group_id
        : null,
    visit_group_id:
      intent.visit_group_id &&
      (visitCounts.get(intent.visit_group_id) ?? 0) >= 2
        ? intent.visit_group_id
        : null,
  }));
}

function relationshipGroupId(
  mode: Exclude<RelationshipMode, "independent">,
  locationIds: string[],
): string {
  let hash = 2166136261;
  for (const character of locationIds.join("|")) {
    hash = Math.imul(hash ^ character.charCodeAt(0), 16777619);
  }
  return `${mode === "either_or" ? "choice" : "together"}-${(hash >>> 0).toString(36)}`;
}

function relationshipGroups(intents: PoiIntentDto[]): Array<{
  id: string;
  kind: "either_or" | "visit_group";
  locationIds: string[];
}> {
  const groups = new Map<
    string,
    { id: string; kind: "either_or" | "visit_group"; locationIds: string[] }
  >();
  for (const intent of intents) {
    const id = intent.either_or_group_id ?? intent.visit_group_id;
    if (!id) continue;
    const kind = intent.either_or_group_id ? "either_or" : "visit_group";
    const key = `${kind}:${id}`;
    const group = groups.get(key) ?? { id, kind, locationIds: [] };
    group.locationIds.push(intent.location_id);
    groups.set(key, group);
  }
  return [...groups.values()];
}

function SessionStatus({ session }: { session: PreplanningSessionDto }) {
  return (
    <div className="f009-session" role="status">
      <span>状态：{session.state}</span>
      <span>revision：{session.revision}</span>
      <span>
        调用：POI {session.calls.poi_search}/25 · 逆地理{" "}
        {session.calls.reverse_geocode}/4 · 路线 {session.calls.route}/24
      </span>
    </div>
  );
}

function V6PreflightResult({
  result,
  intents,
  options,
  selectedOptionId,
  onSelectOption,
  onRecovery,
  dayCount,
}: {
  result: PreflightV6Dto;
  intents: PoiIntentDto[];
  options: PoiOptionDto[];
  selectedOptionId: string | null;
  onSelectOption(optionId: string): void;
  onRecovery(input: Parameters<F009Api["applyRecoveryAction"]>[3]): void;
  dayCount: number;
}) {
  const selectedOption =
    result.options.find((option) => option.option_id === selectedOptionId) ??
    result.options[0];
  const plannedIds = new Set(
    selectedOption?.days.flatMap((day) =>
      day.stops.map((stop) => stop.location_id),
    ) ?? [],
  );
  return (
    <div className="f009-preflight" role="status">
      <strong>
        {result.state === "feasible" ? "预检可行" : "预检尚不可行"}
      </strong>
      <SelectionPlanSummary
        selectedCount={intents.length}
        plannedIds={plannedIds}
        intents={intents}
        options={options}
        hasPlan={Boolean(selectedOption)}
      />
      {result.options.length > 0 && (
        <fieldset className="f015-plan-options">
          <legend>
            {result.options.length === 1
              ? "当前找到 1 个具有明显取舍的可行方案"
              : `比较 ${result.options.length} 个具有不同取舍的可行方案`}
          </legend>
          <p className="f018-option-help">
            总交通相同时，请继续比较每天安排、最忙一天和偏好偏离；地点、路线和时间均已通过确定性预检。
          </p>
          {result.options.map((option) => (
            <PlanOptionCard
              key={option.option_id}
              option={option}
              checked={option.option_id === selectedOption?.option_id}
              onSelect={onSelectOption}
            />
          ))}
        </fieldset>
      )}
      {selectedOption?.days.map((day) => (
        <div key={day.local_date}>
          <b>{day.local_date}</b> · {day.stops.length} 个地点 · 交通{" "}
          {day.total_transport_minutes} 分钟
          <ul>
            {day.routes.map((route) => (
              <li key={route.route_id}>
                {route.mode === "walking" ? "步行" : "公交"}{" "}
                {route.distance_meters} m / {route.duration_minutes} 分钟
              </li>
            ))}
          </ul>
        </div>
      ))}
      {result.conflicts.map((conflict) => (
        <div
          className="f015-conflict-recovery"
          key={`${conflict.code}-${conflict.message}`}
        >
          <p>
            <b>需要你确认调整</b>：{conflict.message}
          </p>
          {conflict.location_ids[0] && (
            <div>
              {dayCount > 1 && (
                <button
                  type="button"
                  onClick={() =>
                    onRecovery({
                      action: "move_to_day",
                      location_id: conflict.location_ids[0],
                      target_day: 1,
                    })
                  }
                >
                  尝试改到第 2 天
                </button>
              )}
              <button
                type="button"
                onClick={() =>
                  onRecovery({
                    action: "shorten_visit",
                    location_id: conflict.location_ids[0],
                    duration_minutes: 60,
                  })
                }
              >
                缩短为 60 分钟
              </button>
              {intents.find(
                (intent) => intent.location_id === conflict.location_ids[0],
              )?.importance === "optional" && (
                <button
                  type="button"
                  onClick={() =>
                    onRecovery({
                      action: "allow_omission",
                      location_id: conflict.location_ids[0],
                    })
                  }
                >
                  允许省略这个可选地点
                </button>
              )}
              {intents.find(
                (intent) => intent.location_id === conflict.location_ids[0],
              )?.either_or_group_id ||
              intents.find(
                (intent) => intent.location_id === conflict.location_ids[0],
              )?.visit_group_id ? (
                <button
                  type="button"
                  onClick={() =>
                    onRecovery({
                      action: "unlink_group",
                      location_id: conflict.location_ids[0],
                    })
                  }
                >
                  解除这组地点关系
                </button>
              ) : null}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function PlanOptionCard({
  option,
  checked,
  onSelect,
}: {
  option: PlanOptionV6Dto;
  checked: boolean;
  onSelect(optionId: string): void;
}) {
  const busiestDay = Math.max(
    ...option.days.map((day) => day.total_transport_minutes),
  );
  return (
    <label className="f015-plan-option" data-selected={checked}>
      <input
        type="radio"
        name="v6-plan-option"
        checked={checked}
        onChange={() => onSelect(option.option_id)}
      />
      <span>
        <strong>{option.title}</strong>
        <small>{option.explanation}</small>
        <em>
          交通 {option.total_transport_minutes} 分钟 · 偏好覆盖{" "}
          {option.preference_coverage_score}% · 最忙一天交通 {busiestDay} 分钟 ·{" "}
          {option.weather_message}
        </em>
        <ul className="f018-option-days">
          {option.days.map((day, index) => (
            <li key={day.local_date}>
              <b>第 {index + 1} 天</b>
              <span>{day.stops.map((stop) => stop.name).join(" → ")}</span>
              <small>交通 {day.total_transport_minutes} 分钟</small>
            </li>
          ))}
        </ul>
        {option.preferred_day_deviation > 0 && (
          <small className="f018-option-warning">
            有 {option.preferred_day_deviation} 项日期偏好未完全满足
          </small>
        )}
      </span>
    </label>
  );
}

function AgentPlanResult({
  result,
  mapPlan,
  intents,
  options,
  onRetryNarrative,
  retrying,
}: {
  result: TripPlanAgentResponseDto;
  mapPlan: MapPlanDto | null;
  intents: PoiIntentDto[];
  options: PoiOptionDto[];
  onRetryNarrative(): void;
  retrying: boolean;
}) {
  const locations = new Map(
    result.plan?.locations.map((item) => [item.location_id, item.name]),
  );
  const intentByLocation = new Map(
    intents.map((intent) => [intent.location_id, intent]),
  );
  const narrativeUnavailable = result.errors.some(
    (error) => error.code === "model_output_invalid",
  );
  const plannedIds = new Set(
    result.plan?.days.flatMap((day) =>
      day.stops.map((stop) => stop.location_id),
    ) ?? [],
  );
  return (
    <section className="f009-result" aria-labelledby="f009-result-title">
      <h3 id="f009-result-title" data-f010-step-heading tabIndex={-1}>
        行程已生成
      </h3>
      <SelectionPlanSummary
        selectedCount={result.request_summary.selected_poi_count}
        plannedIds={plannedIds}
        intents={intents}
        options={options}
        hasPlan={result.plan !== null}
      />
      {result.response_version === "6" && result.plan && (
        <p className="f015-weather-status" role="status">
          <strong>天气信息：</strong>
          {result.plan.weather_message}
          {result.plan.weather_status === "verified"
            ? "，已纳入顾问提示。"
            : "，当前计划不会据此猜测或改动。"}
        </p>
      )}
      {narrativeUnavailable && (
        <aside className="f011-narrative-status" aria-live="polite">
          <div>
            <strong>AI 游览提示暂不可用</strong>
            <p>地点、日期、时间、路线和这份计划仍然有效。</p>
          </div>
          {result.retryable && (
            <button
              type="button"
              onClick={onRetryNarrative}
              disabled={retrying}
            >
              {retrying ? "正在重试…" : "重试 AI 游览提示"}
            </button>
          )}
        </aside>
      )}
      {(result.errors.length > 0 || result.warnings.length > 0) && (
        <details className="f010-model-diagnostic">
          <summary>查看技术详情</summary>
          {result.warnings.map((warning) => (
            <p key={warning}>{warning}</p>
          ))}
          {result.errors.map((error) => (
            <dl key={`${error.code}-${error.diagnostic_code}`}>
              <div>
                <dt>阶段</dt>
                <dd>
                  {error.diagnostic_code?.includes("_repair_")
                    ? "repair"
                    : "generation"}
                </dd>
              </div>
              <div>
                <dt>Provider</dt>
                <dd>{error.provider ?? "model"}</dd>
              </div>
              <div>
                <dt>诊断码</dt>
                <dd>{error.diagnostic_code ?? error.code}</dd>
              </div>
              <div>
                <dt>可重试</dt>
                <dd>{error.retryable ? "true" : "false"}</dd>
              </div>
            </dl>
          ))}
        </details>
      )}
      {result.plan?.days.map((day, dayIndex) => (
        <article className="f011-day" key={day.local_date}>
          <header className="f011-day-heading">
            <span>DAY {String(dayIndex + 1).padStart(2, "0")}</span>
            <div>
              <h4>
                第 {dayIndex + 1} 日 · {day.local_date}
              </h4>
              {day.pace_note && (
                <div className="f017-day-advice">
                  <small>旅行顾问建议</small>
                  <p>{day.pace_note}</p>
                </div>
              )}
            </div>
          </header>
          <DayTimeline
            day={day}
            dayIndex={dayIndex}
            accommodationName={result.plan?.accommodation.label ?? "住宿"}
            locations={locations}
            intentByLocation={intentByLocation}
          />
        </article>
      ))}
      {!mapPlan && (
        <p className="f011-map-note" role="status">
          地图路线暂不可用；上方完整时间轴不受影响。
        </p>
      )}
    </section>
  );
}

function SelectionPlanSummary({
  selectedCount,
  plannedIds,
  intents,
  options,
  hasPlan,
}: {
  selectedCount: number;
  plannedIds: ReadonlySet<string>;
  intents: PoiIntentDto[];
  options: PoiOptionDto[];
  hasPlan: boolean;
}) {
  const names = new Map(
    options.map((option) => [option.location_id, option.name]),
  );
  const omitted = intents.filter(
    (intent) => !plannedIds.has(intent.location_id),
  );
  const eitherGroupsWithPlannedMember = new Set(
    intents
      .filter(
        (intent) =>
          intent.either_or_group_id && plannedIds.has(intent.location_id),
      )
      .map((intent) => intent.either_or_group_id as string),
  );
  return (
    <section className="f013-plan-summary" aria-label="选点与安排摘要">
      <dl>
        <div>
          <dt>已选择地点</dt>
          <dd>{selectedCount}</dd>
        </div>
        <div>
          <dt>实际安排地点</dt>
          <dd>{hasPlan ? plannedIds.size : "尚未形成"}</dd>
        </div>
        <div>
          <dt>未采用地点</dt>
          <dd>{hasPlan ? omitted.length : "待预检"}</dd>
        </div>
      </dl>
      {hasPlan && omitted.length > 0 && (
        <ul>
          {omitted.map((intent) => {
            const eitherOr =
              intent.either_or_group_id &&
              eitherGroupsWithPlannedMember.has(intent.either_or_group_id);
            return (
              <li key={intent.location_id}>
                <strong>{names.get(intent.location_id) ?? "已选地点"}</strong>：
                {eitherOr
                  ? "二选一未采用，同行地点已进入计划"
                  : intent.omission_allowed
                    ? "按你的允许省略设置未安排"
                    : "尚未安排，请返回预检处理"}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

type PlanDay = NonNullable<TripPlanAgentResponseDto["plan"]>["days"][number];

function DayTimeline({
  day,
  dayIndex,
  accommodationName,
  locations,
  intentByLocation,
}: {
  day: PlanDay;
  dayIndex: number;
  accommodationName: string;
  locations: ReadonlyMap<string, string>;
  intentByLocation: ReadonlyMap<string, PoiIntentDto>;
}) {
  return (
    <ol className="f011-timeline" aria-label={`第 ${dayIndex + 1} 日行程`}>
      <li className="f011-timeline-stop f011-timeline-lodging">
        <span className="f011-timeline-marker">住</span>
        <div>
          <small>当天起点</small>
          <strong>{accommodationName}</strong>
          <p>从住宿出发</p>
        </div>
      </li>
      {day.stops.map((stop, index) => {
        const route = day.routes[index];
        const intent = intentByLocation.get(stop.location_id);
        return (
          <li className="f011-timeline-pair" key={stop.location_id}>
            {route && <RouteTimelineItem route={route} locations={locations} />}
            <div className="f011-timeline-stop">
              <span className="f011-timeline-marker">{stop.visit_order}</span>
              <div>
                <small>
                  {stop.start_time.slice(0, 5)}—{stop.end_time.slice(0, 5)}
                </small>
                <strong>{locations.get(stop.location_id)}</strong>
                <div className="f011-stop-tags">
                  <span>
                    {stop.importance === "must_visit" ? "必去" : "可选"}
                  </span>
                  <span>
                    预计{" "}
                    {intent?.expected_duration_minutes ?? elapsedMinutes(stop)}{" "}
                    分钟
                  </span>
                  {intent?.preferred_day != null && (
                    <span>偏好第 {intent.preferred_day + 1} 日</span>
                  )}
                </div>
                {stop.narrative && (
                  <p className="f017-stop-advice">
                    <span>顾问提示</span>
                    {stop.narrative}
                  </p>
                )}
              </div>
            </div>
          </li>
        );
      })}
      {day.routes[day.stops.length] && (
        <li className="f011-timeline-pair">
          <RouteTimelineItem
            route={day.routes[day.stops.length]}
            locations={locations}
          />
          <div className="f011-timeline-stop f011-timeline-lodging">
            <span className="f011-timeline-marker">住</span>
            <div>
              <small>当天终点</small>
              <strong>{accommodationName}</strong>
              <p>返回住宿</p>
            </div>
          </div>
        </li>
      )}
    </ol>
  );
}

function RouteTimelineItem({
  route,
  locations,
}: {
  route: PlanDay["routes"][number];
  locations: ReadonlyMap<string, string>;
}) {
  return (
    <div className="f011-timeline-route">
      <span aria-hidden="true">↓</span>
      <p>
        {route.mode === "walking" ? "步行" : "公共交通"} ·{" "}
        {formatDistance(route.distance_meters)} · {route.duration_minutes} 分钟
      </p>
      <span className="sr-only">
        {locations.get(route.origin_location_id) ?? "住宿"}前往
        {locations.get(route.destination_location_id) ?? "住宿"}
      </span>
    </div>
  );
}

function formatDistance(meters: number): string {
  return meters < 1000 ? `${meters} 米` : `${(meters / 1000).toFixed(1)} 公里`;
}

function elapsedMinutes(stop: PlanDay["stops"][number]): number {
  const [startHour, startMinute] = stop.start_time.split(":").map(Number);
  const [endHour, endMinute] = stop.end_time.split(":").map(Number);
  return endHour * 60 + endMinute - (startHour * 60 + startMinute);
}

function accommodationChoice(
  mode: AccommodationChoiceDto["mode"],
  options: PoiOptionDto[],
  selectedId: string | null,
  pin: { location_id: string; label: string } | null,
  areaLabel: string,
): AccommodationChoiceDto | null {
  if (mode === "map_pin")
    return pin
      ? {
          mode,
          label: pin.label,
          confidence: "area_estimate",
          semantic_location_id: null,
          route_anchor_location_id: pin.location_id,
        }
      : null;
  const selected = options.find((option) => option.location_id === selectedId);
  if (!selected) return null;
  return mode === "exact_poi"
    ? {
        mode,
        label: selected.name,
        confidence: "exact",
        semantic_location_id: selected.location_id,
        route_anchor_location_id: selected.location_id,
      }
    : {
        mode,
        label: areaLabel,
        confidence: "area_estimate",
        semantic_location_id: selected.location_id,
        route_anchor_location_id: selected.location_id,
      };
}

function uniqueOptions(options: PoiOptionDto[]): PoiOptionDto[] {
  return [
    ...new Map(options.map((option) => [option.location_id, option])).values(),
  ];
}

function withDates(
  trip: PreplanningTripDto,
  start: string,
  end: string,
): PreplanningTripDto {
  const dayCount = Math.max(
    0,
    Math.round(
      (Date.parse(`${end}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) /
        86_400_000,
    ) + 1,
  );
  return {
    ...trip,
    start_date: start,
    end_date: end,
    day_windows: Array.from({ length: dayCount }, (_, day_offset) => ({
      day_offset,
      start_time: "09:00:00",
      end_time: "20:00:00",
    })),
  };
}

class SaveConflictError extends Error {}

function isRevisionConflict(error: unknown): boolean {
  return (
    error instanceof F009ClientError &&
    error.code === "selection_revision_conflict"
  );
}

function userFacingError(error: unknown): string {
  if (!(error instanceof F009ClientError)) {
    return "本地请求未完成，请检查服务状态后重试。";
  }
  if (error.code === "session_expired" || error.code === "session_not_found") {
    return "本次选点会话已过期，请重新开始地点选择。";
  }
  if (error.code === "selection_revision_conflict") {
    return "规划信息已发生变化，请确认最新选择后重新保存。";
  }
  if (error.code === "selection_invalid" || error.code === "invalid_request") {
    return "地点关系或住宿信息未通过校验，请检查后重试。";
  }
  return "本地请求暂时无法完成，请稍后重试。";
}

function saveErrorMessage(error: unknown): string {
  if (!(error instanceof F009ClientError)) {
    return "旅行信息暂时无法保存，请检查本地服务后重试。";
  }
  if (error.code === "session_expired" || error.code === "session_not_found") {
    return "本次选点会话已过期，请重新开始地点选择。";
  }
  if (error.code === "selection_invalid" || error.code === "invalid_request") {
    return "地点关系或住宿信息未通过校验，请检查后重新保存。";
  }
  if (error.code === "selection_revision_conflict") {
    return "规划信息已发生变化，请确认最新选择后重新保存。";
  }
  return "旅行信息暂时无法保存，请稍后重试。";
}

function safeErrorCode(error: unknown): string {
  if (!(error instanceof F009ClientError)) return "request_failed";
  return [
    "selection_revision_conflict",
    "selection_invalid",
    "invalid_request",
    "session_expired",
    "session_not_found",
    "invalid_response",
  ].includes(error.code)
    ? error.code
    : "request_failed";
}

function sameValue(left: unknown, right: unknown): boolean {
  return JSON.stringify(sortValue(left)) === JSON.stringify(sortValue(right));
}

function sortValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortValue);
  if (typeof value !== "object" || value === null) return value;
  return Object.fromEntries(
    Object.entries(value)
      .sort(([left], [right]) => left.localeCompare(right))
      .map(([key, item]) => [key, sortValue(item)]),
  );
}

function validateSaveInput(
  trip: PreplanningTripDto,
  selection: PreplanningSelectionDto,
): string | null {
  const start = Date.parse(`${trip.start_date}T00:00:00Z`);
  const end = Date.parse(`${trip.end_date}T00:00:00Z`);
  const dayCount =
    Number.isFinite(start) && Number.isFinite(end)
      ? Math.round((end - start) / 86_400_000) + 1
      : 0;
  if (dayCount < 2 || dayCount > 7 || trip.day_windows.length !== dayCount) {
    return "旅行日期必须连续选择 2–7 天。";
  }
  if (!selection.accommodation.route_anchor_location_id) {
    return "请先确认每天出发和返回的住宿位置。";
  }
  if (selection.pois.length < 1 || selection.pois.length > 8) {
    return "请选择 1–8 个想去的地点。";
  }
  const eitherGroups = new Map<string, PoiIntentDto[]>();
  const visitGroups = new Map<string, PoiIntentDto[]>();
  for (const intent of selection.pois) {
    if (intent.either_or_group_id && intent.visit_group_id) {
      return "同一个地点不能同时设为二选一和一起游览。";
    }
    const duration = intent.expected_duration_minutes;
    if (
      duration != null &&
      (duration < 30 || duration > 480 || duration % 15 !== 0)
    ) {
      return "预计游览时长必须为 30–480 分钟，并按 15 分钟递增。";
    }
    if (
      intent.preferred_day != null &&
      (intent.preferred_day < 0 || intent.preferred_day >= dayCount)
    ) {
      return `偏好日必须在本次行程的第 1–${dayCount} 天内。`;
    }
    if (intent.either_or_group_id) {
      const members = eitherGroups.get(intent.either_or_group_id) ?? [];
      members.push(intent);
      eitherGroups.set(intent.either_or_group_id, members);
    }
    if (intent.visit_group_id) {
      const members = visitGroups.get(intent.visit_group_id) ?? [];
      members.push(intent);
      visitGroups.set(intent.visit_group_id, members);
    }
  }
  for (const members of [...eitherGroups.values(), ...visitGroups.values()]) {
    if (members.length < 2) return "每个地点关系至少需要两个地点。";
    if (new Set(members.map((item) => item.importance)).size !== 1) {
      return "同一地点关系内的优先级必须一致。";
    }
  }
  for (const members of visitGroups.values()) {
    const preferredDays = new Set(
      members.map((item) => item.preferred_day ?? null),
    );
    if (preferredDays.size !== 1) {
      return "一起游览的地点必须使用相同偏好日，或全部不指定。";
    }
  }
  return null;
}

function advisorRecommendationRequested(message: string): boolean {
  const normalized = message.trim().toLowerCase();
  if (normalized.includes("不推荐")) return false;
  return [
    "推荐",
    "有什么好玩",
    "有哪些好玩",
    "哪里好玩",
    "值得去",
    "景点",
  ].some((marker) => normalized.includes(marker));
}

function advisorDiscoveryKeywords(message: string): string {
  if (
    ["自然", "山水", "洞", "湖", "公园"].some((item) => message.includes(item))
  ) {
    return "自然景点";
  }
  if (
    ["历史", "文化", "古迹", "博物馆"].some((item) => message.includes(item))
  ) {
    return "文化景点";
  }
  if (["亲子", "儿童", "孩子"].some((item) => message.includes(item))) {
    return "亲子景点";
  }
  return "景点";
}

const defaultTrip: PreplanningTripDto = withDates(
  {
    city: "杭州",
    start_date: "2026-10-01",
    end_date: "2026-10-02",
    travelers: 2,
    total_budget: { amount: "3000", currency: "CNY" },
    one_night_cost: { amount: "500", currency: "CNY" },
    meal_budget_per_person_per_day: { amount: "100", currency: "CNY" },
    preferences: { interests: [], free_text: "", hard_constraints: [] },
    pace: "balanced",
    transport_modes: ["public_transit", "walking"],
    day_windows: [],
  },
  "2026-10-01",
  "2026-10-02",
);
