import type { SVGProps } from "react";

const base = { width: 18, height: 18, viewBox: "0 0 20 20", fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };

export function SparkleIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <path d="M10 2.5 11.6 7.4 16.5 9l-4.9 1.6L10 15.5l-1.6-4.9L3.5 9l4.9-1.6L10 2.5Z" />
      <path d="M16 14.5 16.6 16.4 18.5 17 16.6 17.6 16 19.5 15.4 17.6 13.5 17 15.4 16.4 16 14.5Z" />
    </svg>
  );
}

export function TrashIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <path d="M4 5.5h12" />
      <path d="M7.5 5.5V4a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1.5" />
      <path d="M5.5 5.5 6 16a1 1 0 0 0 1 1h6a1 1 0 0 0 1-1l.5-10.5" />
    </svg>
  );
}

export function CopyIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <rect x="7.5" y="7.5" width="9" height="10" rx="1.5" />
      <path d="M13 7.5V4.5a1 1 0 0 0-1-1h-7a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1H6.5" />
    </svg>
  );
}

export function CheckIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <path d="m4 10.5 4 4 8-9" />
    </svg>
  );
}

export function RefreshIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <path d="M16 5v4h-4" />
      <path d="M4 15v-4h4" />
      <path d="M15.3 8a5.5 5.5 0 0 0-9.6-2.2L4 8" />
      <path d="M4.7 12a5.5 5.5 0 0 0 9.6 2.2L16 12" />
    </svg>
  );
}
