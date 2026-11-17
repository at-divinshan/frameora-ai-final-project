// Local bubbling handler: no document listeners and no desktop sidebar changes.
export function dismissWithEscape(event, open, close, trigger, mobileOnly = false) {
  if (event.key !== 'Escape' || !open || event.defaultPrevented) return;
  if (mobileOnly && !window.matchMedia('(max-width: 760px)').matches) return;
  event.preventDefault();
  event.stopPropagation();
  close();
  trigger.current?.focus();
}
