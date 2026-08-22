import type { SVGProps } from "react";

/**
 * Minimal inline line-icon set for the app shell nav -- hand-drawn rather
 * than a new icon-library dependency (the project already avoids adding
 * packages where a small amount of local code covers it). 20x20, 1.75
 * stroke, currentColor -- one visual language, sized/colored by the caller.
 */
type IconProps = SVGProps<SVGSVGElement>;

const base = {
  width: 20,
  height: 20,
  viewBox: "0 0 20 20",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function OverviewIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <rect x="2.5" y="10.5" width="3.5" height="7" rx="0.8" />
      <rect x="8.25" y="6" width="3.5" height="11.5" rx="0.8" />
      <rect x="14" y="2.5" width="3.5" height="15" rx="0.8" />
    </svg>
  );
}

export function AnalyzerIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="8.5" cy="8.5" r="5.5" />
      <path d="M12.6 12.6 17 17" />
    </svg>
  );
}

export function UploadIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M10 12.5V3" />
      <path d="M6 6.75 10 2.75l4 4" />
      <path d="M3 13v2.3c0 .94.76 1.7 1.7 1.7h10.6c.94 0 1.7-.76 1.7-1.7V13" />
    </svg>
  );
}

export function CustomersIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <circle cx="7.2" cy="6.8" r="2.6" />
      <path d="M2.5 17c0-2.9 2.1-4.9 4.7-4.9s4.7 2 4.7 4.9" />
      <circle cx="14.2" cy="7.5" r="2.1" />
      <path d="M13.2 12.3c2.15.2 3.8 2.05 3.8 4.3" />
    </svg>
  );
}

export function SellersIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M3 8.2 3.9 3.5h12.2l.9 4.7" />
      <path d="M2.7 8.2c0 1.35 1.02 2.3 2.2 2.3s2.2-.95 2.2-2.3c0 1.35 1 2.3 2.15 2.3s2.15-.95 2.15-2.3c0 1.35 1 2.3 2.15 2.3s2.2-.95 2.2-2.3" />
      <path d="M4.3 10.5V17h11.4v-6.5" />
    </svg>
  );
}

export function ProductsIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M10 2.8 17 6.4v7.2L10 17.2 3 13.6V6.4Z" />
      <path d="M3 6.4 10 10l7-3.6" />
      <path d="M10 10v7.2" />
    </svg>
  );
}

export function GeographyIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M10 17.3s5.6-5.1 5.6-9.3a5.6 5.6 0 0 0-11.2 0c0 4.2 5.6 9.3 5.6 9.3Z" />
      <circle cx="10" cy="8" r="1.9" />
    </svg>
  );
}

export function ModelIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <rect x="6" y="6" width="8" height="8" rx="1" />
      <path d="M10 2.5v2.3M10 15.2v2.3M2.5 10h2.3M15.2 10h2.3M4.6 4.6l1.6 1.6M13.8 13.8l1.6 1.6M15.4 4.6l-1.6 1.6M6.2 13.8l-1.6 1.6" />
    </svg>
  );
}

export function MenuIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M3 5.5h14M3 10h14M3 14.5h14" />
    </svg>
  );
}

export function CollapseIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M12.5 4 7 10l5.5 6" />
    </svg>
  );
}

export function ExternalLinkIcon(props: IconProps) {
  return (
    <svg {...base} {...props}>
      <path d="M8 5H4.7A1.7 1.7 0 0 0 3 6.7v8.6c0 .94.76 1.7 1.7 1.7h8.6c.94 0 1.7-.76 1.7-1.7V12" />
      <path d="M9 11 16.5 3.5" />
      <path d="M12 3.5h4.5V8" />
    </svg>
  );
}
