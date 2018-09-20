// Helpers for manipulating dates

function weekAgo() {
  // Get current date
  let date = new Date();
  // Subtract 7 days
  date.setUTCDate(date.getUTCDate() - 7);
  // Reset time to midnight
  date.setUTCHours(0, 0, 0, 0);
  return date;
}

export { weekAgo };
