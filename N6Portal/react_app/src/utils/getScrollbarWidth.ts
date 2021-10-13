export const getScrollbarWidth = (): string => {
  const measurement = document.createElement('div');
  measurement.style.visibility = 'hidden';
  measurement.style.overflow = 'scroll';
  document.body.appendChild(measurement);
  const scrollbarWidth = measurement.offsetWidth - measurement.clientWidth;
  measurement.parentNode?.removeChild(measurement);
  return scrollbarWidth + 'px';
};
