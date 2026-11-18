export function getStoredUsername(): string | null {
  try {
    const user: unknown = JSON.parse(localStorage.getItem('user') || 'null');
    if (user && typeof user === 'object' && 'username' in user
      && typeof user.username === 'string' && user.username.trim()) {
      return user.username;
    }
  } catch {
    // An old or malformed browser entry must not break the dashboard.
  }
  return null;
}

export function clearAuthStorage() {
  for (const key of ['token', 'token_type', 'user', 'userName']) localStorage.removeItem(key);
}
