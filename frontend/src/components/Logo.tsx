export function Logo({ size = 32 }: { size?: number }) {
  return (
    <img
      src="/assets/baseera-logo-mark.png"
      alt="Baseera"
      width={size}
      height={size}
      style={{ borderRadius: size * 0.22, display: "block", flexShrink: 0, objectFit: "cover" }}
    />
  );
}
