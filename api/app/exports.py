"""Calendar exports with provider-stable identity and RFC 5545 escaping."""
from datetime import timezone
from app.models import utc_now


def escape(value):
    return value.replace('\\', '\\\\').replace('\r', '').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def calendar_event(match):
    def stamp(dt):
        return dt.replace(tzinfo=dt.tzinfo or timezone.utc).astimezone(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Echo Madrid//Fixtures//EN', 'BEGIN:VEVENT',
             f'UID:football-data-{match.external_id}@echo-madrid', f'DTSTAMP:{stamp(utc_now())}',
             f'LAST-MODIFIED:{stamp(match.updated_at or utc_now())}',
             f'DTSTART:{stamp(match.utc_date)}',
             'SUMMARY:' + escape(f'{match.home_team.name} vs {match.away_team.name}'),
             'DESCRIPTION:' + escape(f'football-data.org stored fixture. Status: {match.status}. Kickoff may change. Re-download to update; this file is not a subscription.')]
    if match.status in ('CANCELLED', 'POSTPONED'):
        lines.append('STATUS:CANCELLED')
    else:
        lines.append('STATUS:TENTATIVE' if match.status == 'SCHEDULED' else 'STATUS:CONFIRMED')
    lines += ['END:VEVENT', 'END:VCALENDAR']
    # Fold on UTF-8 octet boundaries, with continuation lines <=75 octets.
    folded = []
    for line in lines:
        chunk = ''
        for char in line:
            if len((chunk + char).encode('utf-8')) > 75:
                folded.append(chunk)
                chunk = ' '
            chunk += char
        folded.append(chunk)
    return '\r\n'.join(folded) + '\r\n'
