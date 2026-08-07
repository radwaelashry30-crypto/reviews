export function Logo({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="url(#vozes-gradient)" />
      <path
        d="M9 12.5c0-.83.67-1.5 1.5-1.5h11c.83 0 1.5.67 1.5 1.5v5c0 .83-.67 1.5-1.5 1.5h-7.2L11 22v-2.9l-.6-.02A1.5 1.5 0 0 1 9 17.5v-5Z"
        fill="white"
        fillOpacity="0.95"
      />
      <circle cx="13" cy="15" r="1.15" fill="#171923" />
      <circle cx="16.5" cy="15" r="1.15" fill="#171923" />
      <circle cx="20" cy="15" r="1.15" fill="#171923" />
      <defs>
        <linearGradient id="vozes-gradient" x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor="#E8863C" />
          <stop offset="1" stopColor="#C4542A" />
        </linearGradient>
      </defs>
    </svg>
  );
}
