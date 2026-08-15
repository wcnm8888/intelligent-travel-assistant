import type { PlanningStatus, TripPlanResponseDto } from "../tripPlanningApi";
import type { CostItemDto, TripPlanDto } from "../tripPlanModels";

export const FIXED_CLIENT_ID = "11111111-1111-4111-8111-111111111111";
export const FIXED_JOB_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const SOURCE_ID = "70000000-0000-4000-8000-000000000001";
const QWEATHER_SOURCE_ID = "70000000-0000-4000-8000-000000000002";
const DEEPSEEK_SOURCE_ID = "70000000-0000-4000-8000-000000000003";
const ACCOMMODATION_ID = "90000000-0000-4000-8000-000000000001";
const WEST_LAKE_ID = "90000000-0000-4000-8000-000000000002";
const MUSEUM_ID = "90000000-0000-4000-8000-000000000003";

export function planningResponse(
  status: PlanningStatus = "draft",
  overrides: Partial<TripPlanResponseDto> = {},
): TripPlanResponseDto {
  return {
    job_id: FIXED_JOB_ID,
    trace_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    client_request_id: FIXED_CLIENT_ID,
    status,
    attempt: 1,
    request_summary: {
      city: "杭州",
      start_date: "2026-08-15",
      end_date: "2026-08-16",
      travelers: 2,
      budget: { amount: "4000.00", currency: "CNY" },
    },
    resolved_destination: null,
    plan: null,
    violations: [],
    warnings: [],
    uncertainties: [],
    sources: [],
    errors: [],
    retryable: false,
    created_at: "2026-08-14T10:00:00+08:00",
    updated_at: "2026-08-14T10:00:01+08:00",
    ...overrides,
  };
}

function costItem(
  id: string,
  category: CostItemDto["category"],
  confidence: CostItemDto["confidence"],
  amount: string | null,
  description: string,
): CostItemDto {
  return {
    cost_id: id,
    category,
    confidence,
    amount: amount === null ? null : { amount, currency: "CNY" },
    description,
    source_ids: confidence === "unknown" ? [] : [SOURCE_ID],
  };
}

function readyPlan(): TripPlanDto {
  return {
    plan_id: "cccccccc-cccc-4ccc-8ccc-ccccccccccc1",
    city_adcode: "330100",
    start_date: "2026-08-15",
    end_date: "2026-08-16",
    locations: [
      {
        location_id: ACCOMMODATION_ID,
        provider: "user",
        provider_place_id: null,
        name: "西湖附近住宿锚点",
        category: "accommodation_anchor",
        address: "synthetic 用户住宿区域",
        city_adcode: "330100",
        coordinates: null,
        source_ids: [SOURCE_ID],
      },
      {
        location_id: WEST_LAKE_ID,
        provider: "amap",
        provider_place_id: "synthetic-west-lake",
        name: "西湖湖滨 synthetic POI",
        category: "scenic_area",
        address: "synthetic 地址",
        city_adcode: "330100",
        coordinates: {
          longitude: "120.1600",
          latitude: "30.2500",
          coordinate_system: "provider_native",
        },
        source_ids: [SOURCE_ID],
      },
      {
        location_id: MUSEUM_ID,
        provider: "amap",
        provider_place_id: "synthetic-museum",
        name: "浙江省博物馆 synthetic POI",
        category: "museum",
        address: "synthetic 地址",
        city_adcode: "330100",
        coordinates: {
          longitude: "120.1400",
          latitude: "30.2600",
          coordinate_system: "provider_native",
        },
        source_ids: [SOURCE_ID],
      },
    ],
    days: [
      {
        local_date: "2026-08-15",
        accommodation_location_id: ACCOMMODATION_ID,
        activities: [
          {
            item_id: "91000000-0000-4000-8000-000000000001",
            location_id: WEST_LAKE_ID,
            title: "西湖湖滨步行",
            start_time: "10:00:00",
            end_time: "12:00:00",
            cost_items: [],
            source_ids: [SOURCE_ID],
          },
        ],
        routes: [
          {
            route_id: "92000000-0000-4000-8000-000000000001",
            origin_location_id: ACCOMMODATION_ID,
            destination_location_id: WEST_LAKE_ID,
            mode: "public_transit",
            distance_meters: 3200,
            duration_minutes: 28,
            fare: null,
            source_ids: [SOURCE_ID],
          },
          {
            route_id: "92000000-0000-4000-8000-000000000002",
            origin_location_id: WEST_LAKE_ID,
            destination_location_id: ACCOMMODATION_ID,
            mode: "public_transit",
            distance_meters: 3200,
            duration_minutes: 30,
            fare: null,
            source_ids: [SOURCE_ID],
          },
        ],
        weather: {
          forecast_date: "2026-08-15",
          location_id: WEST_LAKE_ID,
          condition_day: "多云",
          condition_night: "多云",
          temperature_min_celsius: "26",
          temperature_max_celsius: "34",
          alerts: [],
          source_ids: [SOURCE_ID],
        },
      },
      {
        local_date: "2026-08-16",
        accommodation_location_id: ACCOMMODATION_ID,
        activities: [
          {
            item_id: "91000000-0000-4000-8000-000000000002",
            location_id: MUSEUM_ID,
            title: "浙江省博物馆参观",
            start_time: "10:00:00",
            end_time: "12:00:00",
            cost_items: [],
            source_ids: [SOURCE_ID],
          },
        ],
        routes: [
          {
            route_id: "92000000-0000-4000-8000-000000000003",
            origin_location_id: ACCOMMODATION_ID,
            destination_location_id: MUSEUM_ID,
            mode: "public_transit",
            distance_meters: 4800,
            duration_minutes: 36,
            fare: null,
            source_ids: [SOURCE_ID],
          },
          {
            route_id: "92000000-0000-4000-8000-000000000004",
            origin_location_id: MUSEUM_ID,
            destination_location_id: ACCOMMODATION_ID,
            mode: "public_transit",
            distance_meters: 4800,
            duration_minutes: 38,
            fare: null,
            source_ids: [SOURCE_ID],
          },
        ],
        weather: {
          forecast_date: "2026-08-16",
          location_id: MUSEUM_ID,
          condition_day: "阵雨",
          condition_night: "多云",
          temperature_min_celsius: "25",
          temperature_max_celsius: "32",
          alerts: [],
          source_ids: [SOURCE_ID],
        },
      },
    ],
    budget_summary: {
      budget: { amount: "4000.00", currency: "CNY" },
      known_total: { amount: "2140.00", currency: "CNY" },
      unknown_count: 0,
      assessment: "within_budget",
      cost_items: [
        costItem(
          "93000000-0000-4000-8000-000000000001",
          "accommodation",
          "user_provided",
          "700.00",
          "用户提供的一晚住宿费用",
        ),
        costItem(
          "93000000-0000-4000-8000-000000000002",
          "intercity_transport",
          "user_provided",
          "1000.00",
          "用户提供的城际往返费用",
        ),
        costItem(
          "93000000-0000-4000-8000-000000000003",
          "meal",
          "estimated",
          "400.00",
          "100 元每人每天的两日餐饮估算",
        ),
        costItem(
          "93000000-0000-4000-8000-000000000004",
          "local_transport",
          "estimated",
          "40.00",
          "四个公交路线段的规则估算",
        ),
        costItem(
          "93000000-0000-4000-8000-000000000005",
          "ticket",
          "estimated",
          "0.00",
          "零元活动规则，不代表实时票价",
        ),
      ],
    },
  };
}

export function readyPlanningResponse(): TripPlanResponseDto {
  return planningResponse("ready", {
    resolved_destination: {
      city_name: "杭州市",
      adcode: "330100",
      center: {
        longitude: "120.1551",
        latitude: "30.2741",
        coordinate_system: "provider_native",
      },
      source_ids: [SOURCE_ID],
    },
    plan: readyPlan(),
    sources: [
      {
        source_id: SOURCE_ID,
        provider: "system",
        source_type: "synthetic_fixture",
        provider_record_id: "hangzhou-ui-ready",
        fetched_at: "2026-08-14T10:00:00+08:00",
        valid_until: null,
        freshness: "unknown_validity",
        reference_url: null,
        attributions: [],
        warnings: ["synthetic 测试数据"],
      },
      {
        source_id: QWEATHER_SOURCE_ID,
        provider: "qweather",
        source_type: "qweather_daily_forecast",
        provider_record_id: null,
        fetched_at: "2026-08-14T10:00:00+08:00",
        valid_until: "2026-08-14T16:00:00+08:00",
        freshness: "fresh",
        reference_url: "https://www.qweather.com",
        attributions: ["https://developer.qweather.com/attribution.html"],
        warnings: [],
      },
      {
        source_id: DEEPSEEK_SOURCE_ID,
        provider: "deepseek",
        source_type: "deepseek_plan_candidate",
        provider_record_id: null,
        fetched_at: "2026-08-14T10:00:00+08:00",
        valid_until: null,
        freshness: "unknown_validity",
        reference_url: null,
        attributions: [],
        warnings: ["模型输出没有固定有效期"],
      },
    ],
  });
}

export function partialPlanningResponse(): TripPlanResponseDto {
  const plan = readyPlan();
  const unknownTicket = costItem(
    "93000000-0000-4000-8000-000000000014",
    "ticket",
    "unknown",
    null,
    "门票费用缺少可靠来源",
  );
  return planningResponse("partial", {
    resolved_destination: {
      city_name: "杭州市",
      adcode: "330100",
      center: null,
      source_ids: [SOURCE_ID],
    },
    plan: {
      ...plan,
      plan_id: "cccccccc-cccc-4ccc-8ccc-ccccccccccc2",
      days: [
        { ...plan.days[0], routes: [] },
        { ...plan.days[1], routes: [], weather: null },
      ],
      budget_summary: {
        budget: { amount: "4000.00", currency: "CNY" },
        known_total: { amount: "2100.00", currency: "CNY" },
        unknown_count: 1,
        assessment: "budget_indeterminate",
        cost_items: [
          ...plan.budget_summary.cost_items.slice(0, 3),
          unknownTicket,
        ],
      },
    },
    warnings: ["synthetic 验收数据；路线和第二天天气未验证"],
    uncertainties: [
      {
        code: "route_data_missing",
        message: "全部交通时间均未验证",
        affected_refs: ["cccccccc-cccc-4ccc-8ccc-ccccccccccc2"],
        source_ids: [],
      },
      {
        code: "weather_data_missing",
        message: "第二天没有可用的 synthetic 天气数据",
        affected_refs: ["91000000-0000-4000-8000-000000000002"],
        source_ids: [],
      },
    ],
    sources: readyPlanningResponse().sources,
    errors: [
      {
        code: "provider_timeout",
        message: "路线服务在 synthetic 界面样例中超时",
        field: null,
        provider: "amap",
        retryable: true,
      },
      {
        code: "budget_incomplete",
        message: "门票费用未知，完整预算无法判定",
        field: null,
        provider: null,
        retryable: false,
      },
    ],
    retryable: true,
  });
}
