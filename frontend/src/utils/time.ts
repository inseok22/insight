const KST_TIME_ZONE = 'Asia/Seoul';

type DateTimeInput = string | Date | null | undefined;

function parseDateTime(value: DateTimeInput): Date | null {
  if (!value) return null;
  const parsed = value instanceof Date ? value : new Date(value);
  return Number.isNaN(parsed.getTime()) ? null : parsed;
}

export function formatKstDateTime(value: DateTimeInput, options: { seconds?: boolean } = {}) {
  const parsed = parseDateTime(value);
  if (!parsed) return value && typeof value === 'string' ? value : '-';
  return parsed.toLocaleString('ko-KR', {
    timeZone: KST_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: options.seconds ? '2-digit' : undefined,
    hour12: false,
  });
}

export function formatKstDate(value: DateTimeInput) {
  const parsed = parseDateTime(value);
  if (!parsed) return value && typeof value === 'string' ? value : '-';
  return new Intl.DateTimeFormat('ko-KR', {
    timeZone: KST_TIME_ZONE,
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(parsed);
}

export function formatKstShortDate(value: DateTimeInput) {
  const parsed = parseDateTime(value);
  if (!parsed) return '-';
  const parts = new Intl.DateTimeFormat('ko-KR', {
    timeZone: KST_TIME_ZONE,
    month: '2-digit',
    day: '2-digit',
  }).formatToParts(parsed);
  const month = parts.find((part) => part.type === 'month')?.value ?? '--';
  const day = parts.find((part) => part.type === 'day')?.value ?? '--';
  return `${month}.${day}`;
}
