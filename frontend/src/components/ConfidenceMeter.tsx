interface Props {
  value: number; // 0-1
  color: string;
  size?: number;
}

export function ConfidenceMeter({ value, color, size = 40 }: Props) {
  const radius = (size - 6) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - Math.min(value, 1));

  return (
    <svg width={size} height={size} className="transform -rotate-90">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke="#1f2937"
        strokeWidth={3}
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={3}
        strokeDasharray={circumference}
        strokeDashoffset={offset}
        strokeLinecap="round"
        className="confidence-ring"
      />
      <text
        x={size / 2}
        y={size / 2}
        textAnchor="middle"
        dominantBaseline="central"
        fill={color}
        fontSize={size * 0.25}
        fontFamily="JetBrains Mono"
        transform={`rotate(90 ${size / 2} ${size / 2})`}
      >
        {Math.round(value * 100)}
      </text>
    </svg>
  );
}
