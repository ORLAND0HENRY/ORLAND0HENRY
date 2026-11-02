
import json
import os
import html
import urllib.request
import urllib.error
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


USERNAME = os.getenv("GITHUB_USERNAME", "ORLAND0HENRY")
TOKEN = os.getenv("GITHUB_TOKEN")

OUTPUT_DIR = Path("profile")
GRAPHQL_URL = "https://api.github.com/graphql"

BACKGROUND = "#0d1117"
CARD = "#161b22"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#8b949e"
ACCENT = "#f0b429"
GREEN = "#3fb950"

GRAPHQL_QUERY = """
query (
    $login: String!,
    $yearStart: DateTime!,
    $rollingStart: DateTime!,
    $now: DateTime!
) {
    user(login: $login) {
        login
        name
        followers {
            totalCount
        }

        repositories(
            first: 100,
            ownerAffiliations: OWNER,
            privacy: PUBLIC,
            isFork: false,
            orderBy: {field: UPDATED_AT, direction: DESC}
        ) {
            totalCount
            nodes {
                name
                languages(
                    first: 10,
                    orderBy: {field: SIZE, direction: DESC}
                ) {
                    edges {
                        size
                        node {
                            name
                        }
                    }
                }
            }
        }

        year: contributionsCollection(
            from: $yearStart,
            to: $now
        ) {
            totalCommitContributions
            totalPullRequestContributions
            totalIssueContributions
            contributionCalendar {
                totalContributions
                weeks {
                    contributionDays {
                        date
                        contributionCount
                        color
                        weekday
                    }
                }
            }
        }

        rolling: contributionsCollection(
            from: $rollingStart,
            to: $now
        ) {
            contributionCalendar {
                totalContributions
                weeks {
                    contributionDays {
                        date
                        contributionCount
                        color
                        weekday
                    }
                }
            }
        }
    }
}
"""


def escape(value):
    return html.escape(str(value), quote=True)


def svg_document(width, height, content):
    return f"""<svg xmlns="http://www.w3.org/2000/svg"
        width="{width}" height="{height}"
        viewBox="0 0 {width} {height}"
        role="img">
    <rect width="100%" height="100%" rx="16" fill="{BACKGROUND}"/>
    {content}
</svg>
"""


def write_svg(filename, content):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / filename
    path.write_text(content, encoding="utf-8")
    print(f"Generated {path}")


def fetch_data():
    if not TOKEN:
        raise RuntimeError("GITHUB_TOKEN environment variable is missing.")

    today = date.today()
    year_start = date(today.year, 1, 1)
    rolling_start = today - timedelta(days=364)

    variables = {
        "login": USERNAME,
        "yearStart": f"{year_start.isoformat()}T00:00:00Z",
        "rollingStart": f"{rolling_start.isoformat()}T00:00:00Z",
        "now": datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        ).replace("+00:00", "Z"),
    }

    payload = json.dumps({
        "query": GRAPHQL_QUERY,
        "variables": variables
    }).encode("utf-8")

    request = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "Orlantech-Profile-Analytics",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))

    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API returned HTTP {error.code}: {details}"
        ) from error

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Could not connect to GitHub API: {error.reason}"
        ) from error

    if result.get("errors"):
        raise RuntimeError(
            "GitHub GraphQL error:\n" +
            json.dumps(result["errors"], indent=2)
        )

    user = result.get("data", {}).get("user")

    if not user:
        raise RuntimeError(
            f"GitHub user '{USERNAME}' was not found or could not be accessed."
        )

    return user


def get_days(calendar):
    days = {}

    for week in calendar.get("weeks", []):
        for item in week.get("contributionDays", []):
            days[date.fromisoformat(item["date"])] = item

    return days


def safe_color(value):
    if isinstance(value, str) and len(value) == 7 and value.startswith("#"):
        if all(c in "0123456789abcdefABCDEF" for c in value[1:]):
            return value

    return "#161b22"


def text_element(x, y, value, size=14, color=TEXT, weight="normal"):
    return (
        f'<text x="{x}" y="{y}" fill="{color}" '
        f'font-family="Arial, Helvetica, sans-serif" '
        f'font-size="{size}" font-weight="{weight}">'
        f'{escape(value)}</text>'
    )


def rounded_rect(x, y, width, height, fill=CARD, radius=12, stroke=BORDER):
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
        f'rx="{radius}" fill="{fill}" stroke="{stroke}"/>'
    )


def generate_stats(user):
    today = date.today()
    year = user["year"]
    calendar = year["contributionCalendar"]

    metrics = [
        ("CONTRIBUTIONS", calendar["totalContributions"]),
        ("COMMITS", year["totalCommitContributions"]),
        ("PULL REQUESTS", year["totalPullRequestContributions"]),
        ("ISSUES", year["totalIssueContributions"]),
        ("PUBLIC REPOSITORIES", user["repositories"]["totalCount"]),
        ("FOLLOWERS", user["followers"]["totalCount"]),
    ]

    width = 900
    height = 230
    card_width = 274
    card_height = 78
    gap_x = 16
    gap_y = 14
    start_x = 20
    start_y = 55

    content = text_element(
        22, 32,
        f"GITHUB OVERVIEW  /  {today.year}",
        13, MUTED, "bold"
    )

    for index, (label, value) in enumerate(metrics):
        row = index // 3
        col = index % 3

        x = start_x + col * (card_width + gap_x)
        y = start_y + row * (card_height + gap_y)

        content += rounded_rect(x, y, card_width, card_height)

        content += text_element(
            x + 17, y + 27,
            label,
            11, MUTED, "bold"
        )

        content += text_element(
            x + 17, y + 58,
            f"{value:,}",
            25, TEXT, "bold"
        )

    write_svg(
        "stats.svg",
        svg_document(width, height, content)
    )


def calculate_streak(days):
    today = date.today()

    active_dates = {
        day for day, data in days.items()
        if data.get("contributionCount", 0) > 0
    }

    current_streak = 0

    if today in active_dates:
        cursor = today
    elif today - timedelta(days=1) in active_dates:
        cursor = today - timedelta(days=1)
    else:
        cursor = None

    if cursor:
        while cursor in active_dates:
            current_streak += 1
            cursor -= timedelta(days=1)

    longest_streak = 0
    running_streak = 0

    start = today - timedelta(days=364)

    for offset in range(365):
        current_day = start + timedelta(days=offset)

        if current_day in active_dates:
            running_streak += 1
            longest_streak = max(longest_streak, running_streak)
        else:
            running_streak = 0

    return current_streak, longest_streak, len(active_dates)


def generate_streak(user):
    rolling_calendar = user["rolling"]["contributionCalendar"]
    days = get_days(rolling_calendar)

    current, longest, active_days = calculate_streak(days)

    metrics = [
        ("CURRENT STREAK", current, "days"),
        ("LONGEST STREAK", longest, "days"),
        ("ACTIVE DAYS", active_days, "in the last year"),
    ]

    width = 900
    height = 170
    card_width = 274
    card_height = 90
    gap = 16

    content = text_element(
        22, 32,
        "CONTRIBUTION STREAK  /  LAST 365 DAYS",
        13, MUTED, "bold"
    )

    for index, (label, value, suffix) in enumerate(metrics):
        x = 20 + index * (card_width + gap)
        y = 48

        content += rounded_rect(x, y, card_width, card_height)

        content += text_element(
            x + 17, y + 26,
            label,
            11, MUTED, "bold"
        )

        content += text_element(
            x + 17, y + 62,
            f"{value}",
            27, ACCENT, "bold"
        )

        content += text_element(
            x + 67, y + 61,
            suffix,
            12, MUTED
        )

    write_svg(
        "streak.svg",
        svg_document(width, height, content)
    )


def generate_languages(user):
    totals = defaultdict(int)

    repositories = user["repositories"]["nodes"]

    for repository in repositories:
        languages = repository.get("languages") or {}

        for edge in languages.get("edges", []):
            name = edge["node"]["name"]
            size = edge["size"]
            totals[name] += size

    sorted_languages = sorted(
        totals.items(),
        key=lambda item: item[1],
        reverse=True
    )[:6]

    width = 900
    height = 250

    content = text_element(
        22, 32,
        "LANGUAGE DISTRIBUTION  /  PUBLIC REPOSITORIES",
        13, MUTED, "bold"
    )

    if not sorted_languages:
        content += text_element(
            22, 90,
            "No public repository language data available.",
            15, MUTED
        )
    else:
        total_size = sum(value for _, value in sorted_languages)
        bar_x = 22
        bar_y = 57
        bar_width = 856
        bar_height = 13

        palette = [
            "#3572A5",
            "#f1e05a",
            "#e34c26",
            "#563d7c",
            "#3178c6",
            "#89e051",
        ]

        current_x = bar_x

        for index, (name, size) in enumerate(sorted_languages):
            segment_width = bar_width * size / total_size

            content += (
                f'<rect x="{current_x:.2f}" y="{bar_y}" '
                f'width="{segment_width:.2f}" height="{bar_height}" '
                f'rx="3" fill="{palette[index % len(palette)]}"/>'
            )

            current_x += segment_width

        for index, (name, size) in enumerate(sorted_languages):
            row = index // 2
            col = index % 2

            x = 25 + col * 430
            y = 112 + row * 43

            percentage = size / total_size * 100
            color = palette[index % len(palette)]

            content += (
                f'<circle cx="{x + 5}" cy="{y - 5}" '
                f'r="5" fill="{color}"/>'
            )

            content += text_element(
                x + 20, y,
                name,
                14, TEXT, "bold"
            )

            content += text_element(
                x + 385, y,
                f"{percentage:.1f}%",
                13, MUTED
            )

    write_svg(
        "languages.svg",
        svg_document(width, height, content)
    )


def generate_calendar(user):
    today = date.today()
    year = today.year

    calendar = user["year"]["contributionCalendar"]
    days = get_days(calendar)

    january_first = date(year, 1, 1)
    offset = (january_first.weekday() + 1) % 7

    total_days = (today - january_first).days + 1
    total_weeks = (offset + total_days + 6) // 7

    cell = 11
    gap = 3
    step = cell + gap

    left = 48
    top = 65

    width = max(900, left + total_weeks * step + 25)
    height = 190

    content = text_element(
        22, 30,
        f"CONTRIBUTION ACTIVITY  /  {year}",
        13, MUTED, "bold"
    )

    weekdays = [
        ("Mon", 1),
        ("Wed", 3),
        ("Fri", 5),
    ]

    for label, weekday in weekdays:
        y = top + ((weekday + 1) % 7) * step + 9
        content += text_element(
            10, y,
            label,
            9, MUTED
        )

    previous_month = None

    for day_offset in range(total_days):
        current_day = january_first + timedelta(days=day_offset)

        week_number = (offset + day_offset) // 7
        weekday_row = (current_day.weekday() + 1) % 7

        x = left + week_number * step
        y = top + weekday_row * step

        day_data = days.get(current_day, {})
        count = day_data.get("contributionCount", 0)
        color = safe_color(day_data.get("color"))

        if count == 0:
            color = "#161b22"

        content += (
            f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
            f'rx="2" fill="{color}" stroke="#30363d" stroke-width="0.5">'
            f'<title>{current_day.isoformat()}: {count} contributions</title>'
            f'</rect>'
        )

        if current_day.day == 1:
            month_label = current_day.strftime("%b")

            if month_label != previous_month:
                content += text_element(
                    x - 1, 53,
                    month_label,
                    10, MUTED
                )

                previous_month = month_label

    legend_y = top + 7 * step + 17
    legend_x = max(left + 420, width - 205)

    content += text_element(
        legend_x - 50, legend_y + 9,
        "Less",
        10, MUTED
    )

    legend_colors = [
        "#161b22",
        "#0e4429",
        "#006d32",
        "#26a641",
        "#39d353",
    ]

    for index, color in enumerate(legend_colors):
        x = legend_x + index * 16

        content += (
            f'<rect x="{x}" y="{legend_y}" '
            f'width="11" height="11" rx="2" fill="{color}"/>'
        )

    content += text_element(
        legend_x + 90, legend_y + 9,
        "More",
        10, MUTED
    )

    write_svg(
        "contributions.svg",
        svg_document(width, height, content)
    )


def main():
    print(f"Generating analytics for {USERNAME}...")

    user = fetch_data()

    generate_stats(user)
    generate_streak(user)
    generate_languages(user)
    generate_calendar(user)

    print("All four analytics SVGs generated successfully.")


if __name__ == "__main__":
    main()
