interface LoadingSpinnerProps {
  message?: string;
  size?: "sm" | "md" | "lg";
}

const sizeClasses = {
  sm: "h-5 w-5 border-2",
  md: "h-8 w-8 border-2",
  lg: "h-12 w-12 border-4",
} as const;

export function LoadingSpinner({ message, size = "md" }: LoadingSpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-8">
      <div
        className={`${sizeClasses[size]} animate-spin rounded-full border-gray-300 border-t-blue-600`}
        role="status"
        aria-label="Loading"
      />
      {message && <p className="text-sm text-gray-500">{message}</p>}
    </div>
  );
}
