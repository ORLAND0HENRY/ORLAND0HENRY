
import os
import json
import html
import urllib.request
import urllib.error

from datetime import datetime, timezone, timedelta
from collections import defaultdict
from pathlib import Path


USERNAME = os.getenv("GITHUB_USERNAME", "ORLAND0HENRY")
TOKEN = os.environ["GITHUB_TOKEN"]

OUTPUT = Path("profile")
OUTPUT.mkdir(parents=True, exist_ok=True)

BG = "#0d1117"
CARD = "#111b2a"
ACCENT = "#58e6c8"
TEXT = "#c9d1d9"
MUTED = "#8b949e"
BORDER = "#263341"

WIDTH = 760


QUERY = """
query (
  $login: String!,
  $yearStart: DateTime!,
  $rollingStart: DateTime!,
  $now: DateTime!
) {
  user(login: $login) {
    login
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
        languages(first: 10, orderBy: SIZE) {
          edges {
            size
            node {
              name
              color
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
          }
        }
      }
    }

    rolling: contributionsCollection(
      from: $rollingStart,
      to: $now
    ) {
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


def fetch_data():
    now = datetime.now(timezone.utc).replace(microsecond=0)

    year_start = datetime(
        now.year, 1, 1, tzinfo=timezone.utc
    )

    rolling_start = now - timedelta(days=365)

    variables = {
        "login": USERNAME,
        "yearStart": year_start.isoformat(),
        "rollingStart": rolling_start.isoformat(),
        "now": now.isoformat(),
    }

    payload = json.dumps({
        "query": QUERY,
        "variables": variables
    }).encode()

    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "Accept": "application/vnd.github+json",
            "User-Agent": "Orlantech-Profile-Analytics"
        }
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read())

    except urllib.error.HTTPError as error:
        print(error.read().decode())
        raise RuntimeError(
            f"GitHub API returned HTTP {error.code}"
        ) from error

    if result.get("errors"):
        raise RuntimeError(
            json.dumps(result["errors"], indent=2)
        )

    user = result.get("data", {}).get("user")

    if not user:
        raise RuntimeError(
            f"GitHub user not found: {USERNAME}"
        )

    return user


def escape(value):
    return html.escape(str(value))


def svg_start(title, width=WIDTH, height=200):
    return f'''<svg xmlns="http://www.w3.org/2000/svg"
    width="{width}" height="{height}"
    viewBox="0 0 {width} {height}"
    role="img" aria-label="{escape(title)}">
    <title>{escape(title)}</title>
    <rect width="100%" height="100%" rx="16" fill="{BG}"/>
    '''


def svg_end():
    return "</svg>"


def text(x, y, value, size=13, color=TEXT,
         weight="400", anchor="start"):
    return (
        f'<text x="{x}" y="{y}" '
        f'fill="{color}" font-size="{size}" '
        f'font-family="Arial, Helvetica, sans-serif" '
        f'font-weight="{weight}" text-anchor="{anchor}">'
        f'{escape(value)}</text>'
    )


def card(x, y, width, height):
    return (
        f'<rect x="{x}" y="{y}" width="{width}" '
        f'height="{height}" rx="12" '
        f'fill="{CARD}" stroke="{BORDER}"/>'
    )


def contribution_days(calendar):
    days = []

    for week in calendar["weeks"]:
        for day in week["contributionDays"]:
            days.append({
                "date": datetime.strptime(
                    day["date"], "%Y-%m-%d"
                ).date(),
                "count": day["contributionCount"]
            })

    return sorted(days, key=lambda item: item["date"])


def calculate_streaks(days):
    if not days:
        return 0, 0

    longest = 0
    running = 0

    for day in days:
        if day["count"] > 0:
            running += 1
            longest = max(longest, running)
        else:
            running = 0

    today = datetime.now(timezone.utc).date()
    counts = {
        day["date"]: day["count"]
        for day in days
    }

    current = 0
    cursor = today

    # A contribution yesterday can still represent
    # an active streak before today's contribution.

    if counts.get(cursor, 0) == 0:
        cursor -= timedelta(days=1)

    while counts.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)

    return current, longest


def generate_stats(user):
    year = user["year"]
    repositories = user["repositories"]

    stats = [
        ("CONTRIBUTIONS", year["contributionCalendar"]["totalContributions"]),
        ("COMMITS", year["totalCommitContributions"]),
        ("PULL REQUESTS", year["totalPullRequestContributions"]),
        ("ISSUES", year["totalIssueContributions"]),
        ("PUBLIC REPOS", repositories["totalCount"]),
        ("FOLLOWERS", user["followers"]["totalCount"]),
    ]

    svg = svg_start("GitHub Profile Statistics", height=210)

    svg += text(28, 34, "PROFILE STATISTICS", 12, ACCENT, "bold")
    svg += text(732, 34, str(datetime.now().year), 12, MUTED, anchor="end")

    for index, (label, value) in enumerate(stats):
        column = index % 3
        row = index // 3

        x = 24 + column * 244
        y = 52 + row * 76

        svg += card(x, y, 230, 64)
        svg += text(x + 16, y + 24, label, 10, MUTED, "bold")
        svg += text(x + 16, y + 49, f"{value:,}", 21, ACCENT, "bold")

    svg += svg_end()

    (OUTPUT / "stats.svg").write_text(svg, encoding="utf-8")


def generate_streak(user):
    days = contribution_days(
        user["rolling"]["contributionCalendar"]
    )

    current, longest = calculate_streaks(days)

    active_days = sum(
        1 for day in days if day["count"] > 0
    )

    svg = svg_start("GitHub Contribution Streak", height=190)

    svg += text(28, 35, "CONTRIBUTION STREAK", 12, ACCENT, "bold")
    svg += text(732, 35, "LAST 365 DAYS", 10, MUTED, anchor="end")

    metrics = [
        ("CURRENT STREAK", current, "days"),
        ("LONGEST STREAK", longest, "days"),
        ("ACTIVE DAYS", active_days, "days"),
    ]

    for index, (label, value, suffix) in enumerate(metrics):
        x = 24 + index * 244

        svg += card(x, 55, 230, 95)
        svg += text(x + 115, 87, label, 10, MUTED, "bold", "middle")
        svg += text(
            x + 115, 119, f"{value:,} {suffix}",
            23, ACCENT, "bold", "middle"
        )

    svg += text(
        28, 175,
        "Longest and current streaks calculated from contribution days.",
        10, MUTED
    )

    svg += svg_end()

    (OUTPUT / "streak.svg").write_text(svg, encoding="utf-8")


def generate_languages(user):
    totals = defaultdict(int)
    colors = {}

    repositories = user["repositories"]["nodes"]

    for repository in repositories:
        for edge in repository["languages"]["edges"]:
            language = edge["node"]["name"]

            totals[language] += edge["size"]

            color = edge["node"]["color"]

            if color and color.startswith("#"):
                colors[language] = color

    languages = sorted(
        totals.items(),
        key=lambda item: item[1],
        reverse=True
    )[:6]

    total_bytes = sum(totals.values())

    svg = svg_start("Most Used Programming Languages", height=290)

    svg += text(28, 35, "LANGUAGE BREAKDOWN", 12, ACCENT, "bold")
    svg += text(
        732, 35, "PUBLIC OWNED REPOSITORIES",
        10, MUTED, anchor="end"
    )

    if not languages or not total_bytes:
        svg += text(28, 100, "No language data available yet.", 14)
    else:
        for index, (language, size) in enumerate(languages):
            percentage = size / total_bytes * 100

            y = 76 + index * 33
            color = colors.get(language, ACCENT)

            svg += text(28, y, language, 12, TEXT, "bold")
            svg += text(
                732, y,
                f"{percentage:.1f}%",
                11, MUTED, anchor="end"
            )

            svg += (
                f'<rect x="28" y="{y + 8}" width="704" '
                f'height="7" rx="3.5" fill="{CARD}"/>'
            )

            svg += (
                f'<rect x="28" y="{y + 8}" '
                f'width="{704 * percentage / 100:.2f}" '
                f'height="7" rx="3.5" fill="{color}"/>'
            )

    svg += text(
        28, 272,
        f"Analyzed {len(repositories)} recently updated public repositories.",
        10, MUTED
    )

    svg += svg_end()

    (OUTPUT / "languages.svg").write_text(svg, encoding="utf-8")


def generate_calendar(user):
    year = datetime.now(timezone.utc).year

    calendar = user["year"]["contributionCalendar"]
    days = contribution_days(calendar)

    days = [
        day for day in days
        if day["date"].year == year
    ]

    weeks = {}

    for day in days:
        week_number = (
            day["date"] - datetime(year, 1, 1).date()
        ).days // 7

        weeks.setdefault(week_number, []).append(day)

    max_count = max(
        (day["count"] for day in days),
        default=0
    )

    def cell_color(count):
        if count == 0:
            return "#161b22"

        ratio = count / max_count if max_count else 0

        if ratio <= 0.25:
            return "#0e4429"
        if ratio <= 0.50:
            return "#006d32"
        if ratio <= 0.75:
            return "#26a641"

        return "#39d353"

    svg = svg_start(
        f"{year} GitHub Contribution Calendar",
        width=WIDTH,
        height=160
    )

    svg += text(25, 25, f"{year} CONTRIBUTION ACTIVITY", 12, ACCENT, "bold")

    cell = 10
    gap = 3
    start_x = 35
    start_y = 48

    month_positions = {}

    for day in days:
        date = day["date"]

        week_number = (
            date - datetime(year, 1, 1).date()
        ).days // 7

        x = start_x + week_number * (cell + gap)

        # Sunday-first calendar
        weekday = (date.weekday() + 1) % 7
        y = start_y + weekday * (cell + gap)

        svg += (
            f'<rect x="{x}" y="{y}" width="{cell}" '
            f'height="{cell}" rx="2" '
            f'fill="{cell_color(day["count"])}">'
            f'<title>{date}: {day["count"]} contributions</title>'
            f'</rect>'
        )

        if date.day == 1:
            month_positions[date.month] = x

    for month, x in month_positions.items():
        month_name = datetime(year, month, 1).strftime("%b")
        svg += text(x, 39, month_name, 9, MUTED)

    svg += text(
        25, 142,
        f"{calendar['totalContributions']:,} contributions this year",
        11, TEXT, "bold"
    )

    svg += text(732, 142, "Less", 9, MUTED, anchor="end")

    for index, color in enumerate([
        "#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"
    ]):
        svg += (
            f'<rect x="{635 + index * 15}" y="132" '
            f'width="10" height="10" rx="2" fill="{color}"/>'
        )

    svg += text(732, 155, "More", 9, MUTED, anchor="end")

    svg += svg_end()

    (OUTPUT / "contributions.svg").write_text(
        svg, encoding="utf-8"
    )


def main():
    print(f"Generating analytics for {USERNAME}...")

    user = fetch_data()

    generate_stats(user)
    generate_streak(user)
    generate_languages(user)
    generate_calendar(user)

    print("Successfully generated all analytics SVGs.")

    for filename in OUTPUT.glob("*.svg"):
        print(f"Generated: {filename}")


if __name__ == "__main__":
    main()
