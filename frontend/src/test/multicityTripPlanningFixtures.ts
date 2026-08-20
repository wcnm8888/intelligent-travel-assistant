const SOURCE_ID = "d1000000-0000-4000-8000-000000000001";
const HOTEL_A = "a1000000-0000-4000-8000-000000000001";
const HOTEL_B = "b1000000-0000-4000-8000-000000000001";
const STATION_A = "a2000000-0000-4000-8000-000000000001";
const STATION_B = "b2000000-0000-4000-8000-000000000001";
const ACTIVITY_A = "a3000000-0000-4000-8000-000000000001";
const ACTIVITY_B = "b3000000-0000-4000-8000-000000000001";
const ITEM_A = "a4000000-0000-4000-8000-000000000001";
const ITEM_B = "b4000000-0000-4000-8000-000000000001";
const SEGMENT_ID = "e1000000-0000-4000-8000-000000000001";
const COST_ID = "e2000000-0000-4000-8000-000000000001";
const PLAN_ID = "f1000000-0000-4000-8000-000000000001";

const money = (amount: string) => ({ amount, currency: "CNY" });

function location(id: string, name: string, category: string, adcode: string) {
  return {
    location_id: id,
    provider: "user",
    provider_place_id: null,
    name,
    category,
    address: null,
    city_adcode: adcode,
    coordinates: null,
    source_ids: [SOURCE_ID],
  };
}

function activity(id: string, locationId: string, title: string) {
  return {
    item_id: id,
    location_id: locationId,
    title,
    start_time: "14:00:00",
    end_time: "15:00:00",
    cost_items: [],
    source_ids: [SOURCE_ID],
  };
}

export function multicityPlanningPayload(unknownFare = false): unknown {
  const fare = {
    cost_id: COST_ID,
    category: "intercity_transport",
    confidence: unknownFare ? "unknown" : "user_provided",
    amount: unknownFare ? null : money("120.00"),
    description: "用户提供城际费用",
    source_ids: [SOURCE_ID],
  };
  return {
    response_version: "3",
    job_id: "22222222-2222-4222-8222-222222222222",
    trace_id: "33333333-3333-4333-8333-333333333333",
    client_request_id: "11111111-1111-4111-8111-111111111111",
    status: unknownFare ? "partial" : "ready",
    attempt: 1,
    request_summary: {
      request_version: "3",
      city_stays: [
        { city: "杭州", nights: 1 },
        { city: "上海", nights: 1 },
      ],
      start_date: "2026-08-21",
      end_date: "2026-08-23",
      travelers: 2,
      budget: money("5000.00"),
    },
    resolved_destinations: [
      {
        city_name: "杭州市",
        adcode: "330100",
        center: null,
        source_ids: [SOURCE_ID],
      },
      {
        city_name: "上海市",
        adcode: "310000",
        center: null,
        source_ids: [SOURCE_ID],
      },
    ],
    plan: {
      plan_id: PLAN_ID,
      plan_format_version: "3",
      city_adcodes: ["330100", "310000"],
      start_date: "2026-08-21",
      end_date: "2026-08-23",
      locations: [
        location(HOTEL_A, "杭州住宿", "accommodation_anchor", "330100"),
        location(STATION_A, "杭州站", "rail_station", "330100"),
        location(STATION_B, "上海站", "rail_station", "310000"),
        location(HOTEL_B, "上海住宿", "accommodation_anchor", "310000"),
        location(ACTIVITY_A, "西湖", "attraction", "330100"),
        location(ACTIVITY_B, "外滩", "attraction", "310000"),
      ],
      intercity_segments: [
        {
          segment_id: SEGMENT_ID,
          from_city_index: 0,
          to_city_index: 1,
          mode: "rail",
          departure_station_location_id: STATION_A,
          arrival_station_location_id: STATION_B,
          departure_at: "2026-08-22T10:00:00+08:00",
          arrival_at: "2026-08-22T12:00:00+08:00",
          fare,
          source_ids: [SOURCE_ID],
        },
      ],
      days: [
        {
          local_date: "2026-08-21",
          departure_city_index: 0,
          arrival_city_index: 0,
          overnight_city_index: 0,
          intercity_segment_id: null,
          accommodation_location_id: HOTEL_A,
          activities: [activity(ITEM_A, ACTIVITY_A, "西湖")],
          routes: [],
          weather: null,
        },
        {
          local_date: "2026-08-22",
          departure_city_index: 0,
          arrival_city_index: 1,
          overnight_city_index: 1,
          intercity_segment_id: SEGMENT_ID,
          accommodation_location_id: HOTEL_B,
          activities: [],
          routes: [],
          weather: null,
        },
        {
          local_date: "2026-08-23",
          departure_city_index: 1,
          arrival_city_index: 1,
          overnight_city_index: 1,
          intercity_segment_id: null,
          accommodation_location_id: HOTEL_B,
          activities: [activity(ITEM_B, ACTIVITY_B, "外滩")],
          routes: [],
          weather: null,
        },
      ],
      budget_summary: {
        budget: money("5000.00"),
        known_total: money(unknownFare ? "0.00" : "120.00"),
        unknown_count: unknownFare ? 1 : 0,
        assessment: unknownFare ? "budget_indeterminate" : "within_budget",
        cost_items: [fare],
      },
    },
    violations: [],
    warnings: ["城际段由用户提供，未核验班次、票价、余票或库存"],
    uncertainties: unknownFare
      ? [
          {
            code: "intercity_fare_unknown",
            message: "城际费用未知。",
            affected_refs: [SEGMENT_ID],
            source_ids: [SOURCE_ID],
          },
        ]
      : [],
    sources: [
      {
        source_id: SOURCE_ID,
        provider: "user",
        source_type: "user_provided_intercity_segment",
        provider_record_id: null,
        fetched_at: "2026-08-20T12:00:00+08:00",
        valid_until: null,
        freshness: "unknown_validity",
        reference_url: null,
        attributions: ["用户提供"],
        warnings: ["未核验班次、票价、余票或库存"],
      },
    ],
    errors: [],
    retryable: false,
    created_at: "2026-08-20T12:00:00+08:00",
    updated_at: "2026-08-20T12:01:00+08:00",
  };
}
