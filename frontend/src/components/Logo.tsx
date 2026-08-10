export function Logo({ size = 28 }: { size?: number }) {
  return (
    <span
      style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: size, height: size, borderRadius: size * 0.28, background: "#12100c", flexShrink: 0,
      }}
    >
      <img
        src="/baseera-b-icon.png"
        alt="Baseera"
        width={size * 0.78}
        height={size * 0.78}
        style={{ objectFit: "contain" }}
      />
    </span>
  );
}
