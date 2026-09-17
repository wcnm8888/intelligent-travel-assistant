export type PreplanningState =
  | "draft"
  | "discovering"
  | "needs_confirmation"
  | "prechecking"
  | "feasible"
  | "conflicted"
  | "provider_unavailable"
  | "expired";

export interface Gcj02PointDto {
  longitude: number;
  latitude: number;
}

export interface PoiOptionDto {
  location_id: string;
  provider: "amap";
  provider_place_id: string;
  name: string;
  address: string | null;
  city_adcode: string;
  district_adcode: string;
  category_code: string;
  category_label: string;
  coordinate_gcj02: Gcj02PointDto;
  purpose: "visit" | "accommodation";
  scope_kind: "point" | "area" | "complex";
  confirmation_status: "verified" | "representative_required";
}

export interface PoiIntentDto {
  location_id: string;
  route_anchor_location_id: string;
  importance: "must_visit" | "optional";
  either_or_group_id?: string | null;
  visit_group_id?: string | null;
  preferred_day?: number | null;
  expected_duration_minutes?: number | null;
  omission_allowed: boolean;
  source: "user_selected" | "system_recommendation";
}

export interface AccommodationChoiceDto {
  mode: "area" | "exact_poi" | "map_pin";
  label: string;
  confidence: "exact" | "area_estimate";
  semantic_location_id?: string | null;
  route_anchor_location_id: string;
}

export interface PreplanningSelectionDto {
  accommodation: AccommodationChoiceDto;
  pois: PoiIntentDto[];
  allow_system_recommendations: boolean;
}

export interface PreplanningTripDto {
  city: string;
  start_date: string;
  end_date: string;
  travelers: number;
  total_budget: { amount: string; currency: "CNY" };
  one_night_cost?: { amount: string; currency: "CNY" } | null;
  meal_budget_per_person_per_day?: { amount: string; currency: "CNY" };
  preferences: {
    interests: string[];
    free_text: string;
    hard_constraints: string[];
  };
  pace: "relaxed" | "balanced" | "intensive";
  transport_modes: Array<"walking" | "public_transit">;
  day_windows: Array<{
    day_offset: number;
    start_time: string;
    end_time: string;
  }>;
}

export interface SafeCallsDto {
  poi_search: number;
  reverse_geocode: number;
  route: number;
  total: number;
}

export interface PreplanningSessionDto {
  session_version: "1";
  session_id: string;
  revision: number;
  state: PreplanningState;
  trip: PreplanningTripDto;
  city_adcode: string | null;
  city_name: string | null;
  selection: PreplanningSelectionDto | null;
  calls: SafeCallsDto;
  created_at: string;
  expires_at: string;
  absolute_expires_at: string;
}

export interface PoiSearchResponseDto {
  session_id: string;
  revision: number;
  state: PreplanningState;
  page: number;
  page_size: number;
  has_more: boolean;
  items: PoiOptionDto[];
  calls: SafeCallsDto;
}

export interface FeasibilityConflictDto {
  code: string;
  message: string;
  location_ids: string[];
  route_id: string | null;
  recovery_options: string[];
}

export interface RouteLegDto {
  route_id: string;
  origin_location_id: string;
  destination_location_id: string;
  mode: "walking" | "public_transit";
  straight_line_meters: number;
  distance_meters: number;
  duration_minutes: number;
}

export interface FeasibilityDayDto {
  local_date: string;
  stops: Array<{
    location_id: string;
    route_anchor_location_id: string;
    name: string;
    category: string;
    importance: "must_visit" | "optional";
    expected_duration_minutes: number;
    start_time: string;
    end_time: string;
    preferred_day_satisfied: boolean;
    source: "user_selected" | "system_recommendation";
  }>;
  routes: RouteLegDto[];
  total_transport_minutes: number;
}

export interface PreflightDto {
  session_id: string;
  revision: number;
  state: PreplanningState;
  feasibility_id: string | null;
  days: FeasibilityDayDto[];
  conflicts: FeasibilityConflictDto[];
  calls: SafeCallsDto;
}

export interface PlanOptionV6Dto {
  option_id: string;
  kind: "less_transport" | "relaxed_pace" | "preference_coverage";
  title: string;
  explanation: string;
  days: FeasibilityDayDto[];
  omitted_location_ids: string[];
  total_transport_minutes: number;
  preferred_day_deviation: number;
  preference_coverage_score: number;
  weather_status: "verified" | "not_covered" | "unavailable";
  weather_message: string;
}

export interface PreflightV6Dto {
  response_version: "6";
  session_id: string;
  revision: number;
  state: PreplanningState;
  feasibility_set_id: string | null;
  options: PlanOptionV6Dto[];
  conflicts: FeasibilityConflictDto[];
  calls: SafeCallsDto;
}

export interface TripPlanV5ResponseDto {
  response_version: "5";
  job_id: string;
  trace_id: string;
  client_request_id: string;
  status: "ready" | "partial" | "conflict" | "failed";
  attempt: 1;
  request_summary: {
    request_version: "5";
    city: string;
    start_date: string;
    end_date: string;
    travelers: number;
    budget: { amount: string; currency: "CNY" };
    selected_poi_count: number;
  };
  plan: {
    plan_id: string;
    plan_format_version: "5";
    city_adcode: string;
    start_date: string;
    end_date: string;
    accommodation: AccommodationChoiceDto;
    locations: Array<{
      location_id: string;
      name: string;
      category: string;
      district_adcode: string;
      source: "accommodation" | "user_selected" | "system_recommendation";
    }>;
    days: Array<{
      local_date: string;
      accommodation_location_id: string;
      stops: Array<{
        location_id: string;
        visit_order: number;
        start_time: string;
        end_time: string;
        importance: "must_visit" | "optional";
        narrative: string | null;
      }>;
      routes: Omit<RouteLegDto, "straight_line_meters">[];
      pace_note: string | null;
      rationale: string | null;
    }>;
    global_notes: string[];
  } | null;
  conflicts: FeasibilityConflictDto[];
  warnings: string[];
  errors: Array<{
    code: string;
    message: string;
    field: string | null;
    provider: string | null;
    diagnostic_code?: string;
    retryable: boolean;
  }>;
  retryable: boolean;
  created_at: string;
  updated_at: string;
}

export interface TripPlanV6ResponseDto extends Omit<
  TripPlanV5ResponseDto,
  "response_version" | "request_summary" | "plan"
> {
  response_version: "6";
  request_summary: Omit<
    TripPlanV5ResponseDto["request_summary"],
    "request_version"
  > & {
    request_version: "6";
  };
  plan:
    | (Omit<
        NonNullable<TripPlanV5ResponseDto["plan"]>,
        "plan_format_version"
      > & {
        plan_format_version: "6";
        selected_option_id: string;
        option_kind: "less_transport" | "relaxed_pace" | "preference_coverage";
        weather_status: "verified" | "not_covered" | "unavailable";
        weather_message: string;
      })
    | null;
}

export type TripPlanAgentResponseDto =
  TripPlanV5ResponseDto | TripPlanV6ResponseDto;

export interface MapPlanDto {
  map_version: "1";
  job_id: string;
  plan_id: string;
  coordinate_system: "gcj02";
  accommodation: MapMarkerDto;
  days: Array<{
    local_date: string;
    color_token: string;
    markers: MapMarkerDto[];
    routes: Array<{
      route_id: string;
      origin_location_id: string;
      destination_location_id: string;
      mode: "walking" | "public_transit";
      distance_meters: number;
      duration_minutes: number;
      points: Gcj02PointDto[];
    }>;
  }>;
  warnings: string[];
}

export interface MapMarkerDto {
  location_id: string;
  name: string;
  coordinate: Gcj02PointDto;
  visit_order: number | null;
}

export interface AdvisorPreferencePatchDto {
  walking_tolerance: "low" | "medium" | "high" | null;
  crowd_tolerance: "low" | "medium" | "high" | null;
  day_start: string | null;
  food_preferences: string[];
  budget_flexibility: "fixed" | "small" | "flexible" | null;
  party_notes: string[];
}

export interface AdvisorSuggestionDto {
  suggestion_id: string;
  kind: "preference_patch" | "poi";
  title: string;
  reason: string;
  preference_patch: AdvisorPreferencePatchDto | null;
  location_id: string | null;
  location_name: string | null;
  category: string | null;
}

export interface AdvisorConversationEntryDto {
  role: "user" | "advisor";
  text: string;
}

export interface AdvisorSnapshotDto {
  advisor_version: "1";
  session_id: string;
  revision: number;
  phase: "interview" | "curation" | "ready" | "degraded";
  conversation: AdvisorConversationEntryDto[];
  confirmed_preferences: AdvisorPreferencePatchDto;
  pending_suggestions: AdvisorSuggestionDto[];
  question: string | null;
  safety_summary: string;
}

export class F009ClientError extends Error {
  readonly code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "F009ClientError";
    this.code = code;
  }
}

type RequestFunction = (
  input: RequestInfo | URL,
  init?: RequestInit,
) => Promise<Response>;

export interface F009Api {
  createSession(trip: PreplanningTripDto): Promise<PreplanningSessionDto>;
  getSession(sessionId: string): Promise<PreplanningSessionDto>;
  updateTrip(
    sessionId: string,
    revision: number,
    trip: PreplanningTripDto,
  ): Promise<PreplanningSessionDto>;
  searchPois(
    sessionId: string,
    purpose: "visit" | "accommodation",
    keywords: string,
    filters?: {
      center?: Gcj02PointDto;
      radius_m?: number;
      district_adcode?: string;
      category_codes?: string[];
      page?: number;
      page_size?: number;
    },
  ): Promise<PoiSearchResponseDto>;
  createMapPin(
    sessionId: string,
    revision: number,
    coordinate: Gcj02PointDto,
  ): Promise<{ location_id: string; label: string; coordinate: Gcj02PointDto }>;
  updateSelection(
    sessionId: string,
    revision: number,
    selection: PreplanningSelectionDto,
  ): Promise<PreplanningSessionDto>;
  preflight(sessionId: string, revision: number): Promise<PreflightDto>;
  preflightV6(sessionId: string, revision: number): Promise<PreflightV6Dto>;
  applyRecoveryAction(
    sessionId: string,
    revision: number,
    clientRequestId: string,
    input: {
      action:
        | "move_to_day"
        | "shorten_visit"
        | "allow_omission"
        | "remove_optional"
        | "unlink_group";
      location_id: string;
      target_day?: number;
      duration_minutes?: number;
    },
  ): Promise<PreplanningSessionDto>;
  createPlan(input: {
    client_request_id: string;
    session_id: string;
    selection_revision: number;
    feasibility_id: string;
    trip: PreplanningTripDto;
    selection: PreplanningSelectionDto;
  }): Promise<TripPlanV5ResponseDto>;
  createPlanV6(input: {
    client_request_id: string;
    session_id: string;
    selection_revision: number;
    feasibility_set_id: string;
    option_id: string;
    trip: PreplanningTripDto;
    selection: PreplanningSelectionDto;
  }): Promise<TripPlanV6ResponseDto>;
  retryNarrative(
    jobId: string,
    clientRequestId: string,
    requestVersion?: "5" | "6",
  ): Promise<TripPlanAgentResponseDto>;
  readMap(jobId: string): Promise<MapPlanDto>;
  getAdvisor?(sessionId: string): Promise<AdvisorSnapshotDto>;
  advisorTurn?(
    sessionId: string,
    revision: number,
    clientRequestId: string,
    message: string,
  ): Promise<AdvisorSnapshotDto>;
  advisorAction?(
    sessionId: string,
    revision: number,
    clientRequestId: string,
    suggestionId: string,
    action: "accept" | "ignore",
    selectionContext?: PreplanningSelectionDto | null,
  ): Promise<AdvisorSnapshotDto>;
}

export function createF009Api(
  request: RequestFunction = fetch,
  baseUrl = "",
): F009Api {
  const json = async <T>(path: string, init?: RequestInit): Promise<T> => {
    const response = await request(`${baseUrl}${path}`, init);
    const body: unknown = await response.json().catch(() => null);
    if (!response.ok) {
      const error = readError(body);
      throw new F009ClientError(error.code, error.message);
    }
    return body as T;
  };
  return {
    createSession: (trip) =>
      json("/api/preplanning-sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_version: "1", trip }),
      }),
    getSession: (sessionId) => json(`/api/preplanning-sessions/${sessionId}`),
    updateTrip: (sessionId, revision, trip) =>
      json(`/api/preplanning-sessions/${sessionId}/trip`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: revision, trip }),
      }),
    searchPois: (sessionId, purpose, keywords, filters = {}) => {
      const params = new URLSearchParams({
        purpose,
        keywords,
        page: String(filters.page ?? 1),
        page_size: String(filters.page_size ?? 20),
      });
      if (filters.center) {
        params.set(
          "center",
          `${filters.center.longitude},${filters.center.latitude}`,
        );
      }
      if (filters.radius_m != null)
        params.set("radius_m", String(filters.radius_m));
      if (filters.district_adcode)
        params.set("district_adcode", filters.district_adcode);
      for (const code of filters.category_codes ?? [])
        params.append("category_codes", code);
      return json(
        `/api/preplanning-sessions/${sessionId}/pois?${params.toString()}`,
      );
    },
    createMapPin: (sessionId, revision, coordinate) =>
      json(`/api/preplanning-sessions/${sessionId}/map-pins`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: revision, coordinate }),
      }),
    updateSelection: (sessionId, revision, selection) =>
      json(`/api/preplanning-sessions/${sessionId}/selection`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: revision, selection }),
      }),
    preflight: (sessionId, revision) =>
      json(`/api/preplanning-sessions/${sessionId}/preflight`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expected_revision: revision }),
      }),
    preflightV6: (sessionId, revision) =>
      json(`/api/preplanning-sessions/${sessionId}/v6/preflight`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_version: "6",
          expected_revision: revision,
        }),
      }).then(parsePreflightV6),
    applyRecoveryAction: (sessionId, revision, clientRequestId, input) =>
      json(`/api/preplanning-sessions/${sessionId}/advisor-recovery-actions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_version: "6",
          client_request_id: clientRequestId,
          expected_revision: revision,
          ...input,
        }),
      }),
    createPlan: async (input) =>
      parseTripPlanV5(
        await json<unknown>("/api/trip-plans", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ request_version: "5", ...input }),
        }),
      ),
    createPlanV6: async (input) =>
      parseTripPlanV6(
        await json<unknown>("/api/trip-plans", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ request_version: "6", ...input }),
        }),
      ),
    retryNarrative: async (jobId, clientRequestId, requestVersion = "5") => {
      const raw = await json<unknown>(
        `/api/trip-plans/${jobId}/narrative-retries`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            request_version: requestVersion,
            client_request_id: clientRequestId,
          }),
        },
      );
      return requestVersion === "6"
        ? parseTripPlanV6(raw)
        : parseTripPlanV5(raw);
    },
    readMap: async (jobId) =>
      parseMapPlan(await json<unknown>(`/api/trip-plans/${jobId}/map`)),
    getAdvisor: async (sessionId) =>
      parseAdvisor(
        await json<unknown>(`/api/preplanning-sessions/${sessionId}/advisor`),
      ),
    advisorTurn: async (sessionId, revision, clientRequestId, message) =>
      parseAdvisor(
        await json<unknown>(
          `/api/preplanning-sessions/${sessionId}/advisor-turns`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              advisor_version: "1",
              client_request_id: clientRequestId,
              expected_revision: revision,
              message,
            }),
          },
        ),
      ),
    advisorAction: async (
      sessionId,
      revision,
      clientRequestId,
      suggestionId,
      action,
      selectionContext = null,
    ) =>
      parseAdvisor(
        await json<unknown>(
          `/api/preplanning-sessions/${sessionId}/advisor-actions`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              advisor_version: "1",
              client_request_id: clientRequestId,
              expected_revision: revision,
              suggestion_id: suggestionId,
              action,
              importance: "must_visit",
              selection_context: selectionContext,
            }),
          },
        ),
      ),
  };
}

function parseAdvisor(value: unknown): AdvisorSnapshotDto {
  const snapshot = exactRecord(value, [
    "advisor_version",
    "session_id",
    "revision",
    "phase",
    "conversation",
    "confirmed_preferences",
    "pending_suggestions",
    "question",
    "safety_summary",
  ]);
  literal(snapshot.advisor_version, "1");
  strings(snapshot, ["session_id", "safety_summary"]);
  numbers(snapshot, ["revision"]);
  oneOf(snapshot.phase, ["interview", "curation", "ready", "degraded"]);
  nullableString(snapshot.question);
  arrayOf(snapshot.conversation, (value) => {
    const entry = exactRecord(value, ["role", "text"]);
    oneOf(entry.role, ["user", "advisor"]);
    strings(entry, ["text"]);
  });
  parseAdvisorPreferences(snapshot.confirmed_preferences);
  arrayOf(snapshot.pending_suggestions, (value) => {
    const suggestion = exactRecord(value, [
      "suggestion_id",
      "kind",
      "title",
      "reason",
      "preference_patch",
      "location_id",
      "location_name",
      "category",
    ]);
    strings(suggestion, ["suggestion_id", "title", "reason"]);
    oneOf(suggestion.kind, ["preference_patch", "poi"]);
    nullableString(suggestion.location_id);
    nullableString(suggestion.location_name);
    nullableString(suggestion.category);
    if (suggestion.preference_patch !== null)
      parseAdvisorPreferences(suggestion.preference_patch);
  });
  return snapshot as unknown as AdvisorSnapshotDto;
}

function parseAdvisorPreferences(value: unknown): void {
  const preferences = exactRecord(value, [
    "walking_tolerance",
    "crowd_tolerance",
    "day_start",
    "food_preferences",
    "budget_flexibility",
    "party_notes",
  ]);
  if (preferences.walking_tolerance !== null)
    oneOf(preferences.walking_tolerance, ["low", "medium", "high"]);
  if (preferences.crowd_tolerance !== null)
    oneOf(preferences.crowd_tolerance, ["low", "medium", "high"]);
  if (preferences.budget_flexibility !== null)
    oneOf(preferences.budget_flexibility, ["fixed", "small", "flexible"]);
  nullableString(preferences.day_start);
  stringArray(preferences.food_preferences);
  stringArray(preferences.party_notes);
}

function parsePreflightV6(value: unknown): PreflightV6Dto {
  const response = exactRecord(value, [
    "response_version",
    "session_id",
    "revision",
    "state",
    "feasibility_set_id",
    "options",
    "conflicts",
    "calls",
  ]);
  literal(response.response_version, "6");
  strings(response, ["session_id"]);
  numbers(response, ["revision"]);
  oneOf(response.state, [
    "draft",
    "discovering",
    "needs_confirmation",
    "prechecking",
    "feasible",
    "conflicted",
    "provider_unavailable",
    "expired",
  ]);
  nullableString(response.feasibility_set_id);
  arrayOf(response.conflicts, parseConflict);
  arrayOf(response.options, (value) => {
    const option = exactRecord(value, [
      "option_id",
      "kind",
      "title",
      "explanation",
      "days",
      "omitted_location_ids",
      "total_transport_minutes",
      "preferred_day_deviation",
      "preference_coverage_score",
      "weather_status",
      "weather_message",
    ]);
    strings(option, ["option_id", "title", "explanation", "weather_message"]);
    oneOf(option.kind, [
      "less_transport",
      "relaxed_pace",
      "preference_coverage",
    ]);
    oneOf(option.weather_status, ["verified", "not_covered", "unavailable"]);
    numbers(option, [
      "total_transport_minutes",
      "preferred_day_deviation",
      "preference_coverage_score",
    ]);
    stringArray(option.omitted_location_ids);
    if (!Array.isArray(option.days)) invalidResponse();
  });
  return response as unknown as PreflightV6Dto;
}

function parseTripPlanV6(value: unknown): TripPlanV6ResponseDto {
  const response = exactRecord(value, [
    "response_version",
    "job_id",
    "trace_id",
    "client_request_id",
    "status",
    "attempt",
    "request_summary",
    "plan",
    "conflicts",
    "warnings",
    "errors",
    "retryable",
    "created_at",
    "updated_at",
  ]);
  literal(response.response_version, "6");
  const summary = exactRecord(response.request_summary, [
    "request_version",
    "city",
    "start_date",
    "end_date",
    "travelers",
    "budget",
    "selected_poi_count",
  ]);
  literal(summary.request_version, "6");
  let compatiblePlan: unknown = null;
  if (response.plan !== null) {
    const plan = exactRecord(response.plan, [
      "plan_id",
      "plan_format_version",
      "selected_option_id",
      "option_kind",
      "city_adcode",
      "start_date",
      "end_date",
      "accommodation",
      "locations",
      "days",
      "global_notes",
      "weather_status",
      "weather_message",
    ]);
    literal(plan.plan_format_version, "6");
    strings(plan, ["selected_option_id", "weather_message"]);
    oneOf(plan.option_kind, [
      "less_transport",
      "relaxed_pace",
      "preference_coverage",
    ]);
    oneOf(plan.weather_status, ["verified", "not_covered", "unavailable"]);
    const commonPlan = { ...plan };
    delete commonPlan.selected_option_id;
    delete commonPlan.option_kind;
    delete commonPlan.weather_status;
    delete commonPlan.weather_message;
    compatiblePlan = { ...commonPlan, plan_format_version: "5" };
  }
  parseTripPlanV5({
    ...response,
    response_version: "5",
    request_summary: { ...summary, request_version: "5" },
    plan: compatiblePlan,
  });
  return response as unknown as TripPlanV6ResponseDto;
}

function parseTripPlanV5(value: unknown): TripPlanV5ResponseDto {
  const response = exactRecord(value, [
    "response_version",
    "job_id",
    "trace_id",
    "client_request_id",
    "status",
    "attempt",
    "request_summary",
    "plan",
    "conflicts",
    "warnings",
    "errors",
    "retryable",
    "created_at",
    "updated_at",
  ]);
  literal(response.response_version, "5");
  strings(response, [
    "job_id",
    "trace_id",
    "client_request_id",
    "created_at",
    "updated_at",
  ]);
  oneOf(response.status, ["ready", "partial", "conflict", "failed"]);
  literal(response.attempt, 1);
  booleanValue(response.retryable);
  stringArray(response.warnings);
  const summary = exactRecord(response.request_summary, [
    "request_version",
    "city",
    "start_date",
    "end_date",
    "travelers",
    "budget",
    "selected_poi_count",
  ]);
  literal(summary.request_version, "5");
  strings(summary, ["city", "start_date", "end_date"]);
  numbers(summary, ["travelers", "selected_poi_count"]);
  const budget = exactRecord(summary.budget, ["amount", "currency"]);
  strings(budget, ["amount"]);
  literal(budget.currency, "CNY");
  arrayOf(response.conflicts, parseConflict);
  arrayOf(response.errors, (item) => {
    const error = exactRecord(
      item,
      ["code", "message", "field", "provider", "retryable"],
      ["diagnostic_code"],
    );
    strings(error, ["code", "message"]);
    nullableString(error.field);
    nullableString(error.provider);
    if (error.diagnostic_code !== undefined)
      strings(error, ["diagnostic_code"]);
    booleanValue(error.retryable);
  });
  if (response.plan !== null) parseV5Plan(response.plan);
  return response as unknown as TripPlanV5ResponseDto;
}

function parseV5Plan(value: unknown): void {
  const plan = exactRecord(value, [
    "plan_id",
    "plan_format_version",
    "city_adcode",
    "start_date",
    "end_date",
    "accommodation",
    "locations",
    "days",
    "global_notes",
  ]);
  strings(plan, ["plan_id", "city_adcode", "start_date", "end_date"]);
  literal(plan.plan_format_version, "5");
  parseAccommodation(plan.accommodation);
  arrayOf(plan.locations, (item) => {
    const location = exactRecord(item, [
      "location_id",
      "name",
      "category",
      "district_adcode",
      "source",
    ]);
    strings(location, ["location_id", "name", "category", "district_adcode"]);
    oneOf(location.source, [
      "accommodation",
      "user_selected",
      "system_recommendation",
    ]);
  });
  arrayOf(plan.days, (item) => {
    const day = exactRecord(item, [
      "local_date",
      "accommodation_location_id",
      "stops",
      "routes",
      "pace_note",
      "rationale",
    ]);
    strings(day, ["local_date", "accommodation_location_id"]);
    nullableString(day.pace_note);
    nullableString(day.rationale);
    arrayOf(day.stops, (stopValue) => {
      const stop = exactRecord(stopValue, [
        "location_id",
        "visit_order",
        "start_time",
        "end_time",
        "importance",
        "narrative",
      ]);
      strings(stop, ["location_id", "start_time", "end_time"]);
      numbers(stop, ["visit_order"]);
      oneOf(stop.importance, ["must_visit", "optional"]);
      nullableString(stop.narrative);
    });
    arrayOf(day.routes, parseRoute);
  });
  stringArray(plan.global_notes);
}

function parseMapPlan(value: unknown): MapPlanDto {
  const map = exactRecord(value, [
    "map_version",
    "job_id",
    "plan_id",
    "coordinate_system",
    "accommodation",
    "days",
    "warnings",
  ]);
  literal(map.map_version, "1");
  literal(map.coordinate_system, "gcj02");
  strings(map, ["job_id", "plan_id"]);
  parseMarker(map.accommodation);
  stringArray(map.warnings);
  arrayOf(map.days, (item) => {
    const day = exactRecord(item, [
      "local_date",
      "color_token",
      "markers",
      "routes",
    ]);
    strings(day, ["local_date", "color_token"]);
    arrayOf(day.markers, parseMarker);
    arrayOf(day.routes, (routeValue) => {
      const route = parseRoute(routeValue, ["points"]);
      arrayOf(route.points, parsePoint);
    });
  });
  return map as unknown as MapPlanDto;
}

function parseAccommodation(value: unknown): void {
  const accommodation = exactRecord(value, [
    "mode",
    "label",
    "confidence",
    "semantic_location_id",
    "route_anchor_location_id",
  ]);
  oneOf(accommodation.mode, ["area", "exact_poi", "map_pin"]);
  oneOf(accommodation.confidence, ["exact", "area_estimate"]);
  strings(accommodation, ["label", "route_anchor_location_id"]);
  nullableString(accommodation.semantic_location_id);
}

function parseConflict(value: unknown): void {
  const conflict = exactRecord(value, [
    "code",
    "message",
    "location_ids",
    "route_id",
    "recovery_options",
  ]);
  strings(conflict, ["code", "message"]);
  nullableString(conflict.route_id);
  stringArray(conflict.location_ids);
  stringArray(conflict.recovery_options);
}

function parseMarker(value: unknown): void {
  const marker = exactRecord(value, [
    "location_id",
    "name",
    "coordinate",
    "visit_order",
  ]);
  strings(marker, ["location_id", "name"]);
  if (marker.visit_order !== null) numbers(marker, ["visit_order"]);
  parsePoint(marker.coordinate);
}

function parseRoute(
  value: unknown,
  extraKeys: string[] = [],
): Record<string, unknown> {
  const route = exactRecord(value, [
    "route_id",
    "origin_location_id",
    "destination_location_id",
    "mode",
    "distance_meters",
    "duration_minutes",
    ...extraKeys,
  ]);
  strings(route, ["route_id", "origin_location_id", "destination_location_id"]);
  oneOf(route.mode, ["walking", "public_transit"]);
  numbers(route, ["distance_meters", "duration_minutes"]);
  return route;
}

function parsePoint(value: unknown): void {
  const point = exactRecord(value, ["longitude", "latitude"]);
  numbers(point, ["longitude", "latitude"]);
}

function exactRecord(
  value: unknown,
  keys: string[],
  optionalKeys: string[] = [],
): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    invalidResponse();
  const record = value as Record<string, unknown>;
  const actual = Object.keys(record).sort();
  const required = new Set(keys);
  const allowed = new Set([...keys, ...optionalKeys]);
  if (
    keys.some((key) => !(key in record)) ||
    actual.some((key) => !allowed.has(key)) ||
    actual.length < required.size
  ) {
    invalidResponse();
  }
  return record;
}

function arrayOf(value: unknown, parser: (item: unknown) => void): void {
  if (!Array.isArray(value)) invalidResponse();
  for (const item of value) parser(item);
}

function stringArray(value: unknown): void {
  arrayOf(value, (item) => {
    if (typeof item !== "string") invalidResponse();
  });
}

function strings(record: Record<string, unknown>, keys: string[]): void {
  if (keys.some((key) => typeof record[key] !== "string")) invalidResponse();
}

function numbers(record: Record<string, unknown>, keys: string[]): void {
  if (
    keys.some(
      (key) => typeof record[key] !== "number" || !Number.isFinite(record[key]),
    )
  ) {
    invalidResponse();
  }
}

function oneOf(value: unknown, allowed: readonly unknown[]): void {
  if (!allowed.includes(value)) invalidResponse();
}

function literal(value: unknown, expected: unknown): void {
  if (value !== expected) invalidResponse();
}

function booleanValue(value: unknown): void {
  if (typeof value !== "boolean") invalidResponse();
}

function nullableString(value: unknown): void {
  if (value !== null && typeof value !== "string") invalidResponse();
}

function invalidResponse(): never {
  throw new F009ClientError(
    "invalid_response",
    "服务返回了无法识别的 V5 严格结果。",
  );
}

function readError(value: unknown): { code: string; message: string } {
  if (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof value.error === "object" &&
    value.error !== null &&
    "code" in value.error &&
    "message" in value.error &&
    typeof value.error.code === "string" &&
    typeof value.error.message === "string"
  ) {
    return { code: value.error.code, message: value.error.message };
  }
  return { code: "invalid_response", message: "服务返回了无法识别的结果。" };
}
