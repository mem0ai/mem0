const capitalize = (str: string) => {
    if (!str) return ''
    if (str.length <= 1) return str.toUpperCase()
    return str.toUpperCase()[0] + str.slice(1)
}

function formatDate(timestamp: number) {
    const date = new Date(timestamp * 1000);
    // Format as relative time (e.g., "5 minutes ago", "2 hours ago", "3 days ago")
    const now = new Date();
    const diffInSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffInSeconds < 60) {
      return 'Just Now';
    } else if (diffInSeconds < 3600) {
      const minutes = Math.floor(diffInSeconds / 60);
      return `${minutes} ${minutes === 1 ? 'minute' : 'minutes'} ago`;
    } else if (diffInSeconds < 86400) {
      const hours = Math.floor(diffInSeconds / 3600);
      return `${hours} ${hours === 1 ? 'hour' : 'hours'} ago`;
    } else {
      const days = Math.floor(diffInSeconds / 86400);
      return `${days} ${days === 1 ? 'day' : 'days'} ago`;
    }
  }

export { capitalize, formatDate }