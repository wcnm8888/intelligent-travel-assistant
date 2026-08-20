interface TripDayNavigationProps {
  days: ReadonlyArray<{ local_date: string }>;
  activeDate: string;
  onSelect: (localDate: string) => void;
}

function shortDate(value: string): string {
  const [, month, day] = value.split("-");
  return `${month}.${day}`;
}

export function TripDayNavigation({
  days,
  activeDate,
  onSelect,
}: TripDayNavigationProps) {
  return (
    <nav className="trip-day-navigation" aria-label="行程日期导航">
      <ol>
        {days.map((day, index) => {
          const active = day.local_date === activeDate;
          return (
            <li key={day.local_date}>
              <button
                type="button"
                className={
                  active
                    ? "trip-day-link trip-day-link--active"
                    : "trip-day-link"
                }
                aria-current={active ? "date" : undefined}
                aria-controls={`trip-day-${index + 1}`}
                aria-label={`第 ${index + 1} 天，${day.local_date}${active ? "，当前日期" : ""}`}
                onClick={() => onSelect(day.local_date)}
              >
                <span>{String(index + 1).padStart(2, "0")}</span>
                <strong>{shortDate(day.local_date)}</strong>
                <small>{active ? "当前" : `第 ${index + 1} 天`}</small>
              </button>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}
