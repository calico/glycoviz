import { useCallback, useRef, useState, type DragEvent } from "react";

interface FileUploadDropzoneProps {
  accept: string;
  onUpload: (file: File) => Promise<void>;
  label?: string;
}

export function FileUploadDropzone({
  accept,
  onUpload,
  label = "Drag & drop a file here, or click to browse",
}: FileUploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setSelectedFile(file);
      setError(null);
      setUploading(true);
      setProgress(0);

      // Simulate progress ticks while the upload promise resolves
      const interval = setInterval(() => {
        setProgress((prev) => (prev < 90 ? prev + 10 : prev));
      }, 200);

      try {
        await onUpload(file);
        setProgress(100);
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Upload failed. Please try again.",
        );
      } finally {
        clearInterval(interval);
        setUploading(false);
      }
    },
    [onUpload],
  );

  const handleDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setIsDragOver(false);
      const file = e.dataTransfer.files[0];
      if (file) {
        handleFile(file);
      }
    },
    [handleFile],
  );

  const handleDragOver = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        handleFile(file);
      }
    },
    [handleFile],
  );

  const handleClick = () => {
    if (!uploading) {
      inputRef.current?.click();
    }
  };

  return (
    <div className="w-full">
      <div
        role="button"
        tabIndex={0}
        onClick={handleClick}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") handleClick();
        }}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`
          relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed
          px-6 py-10 transition-colors duration-200 cursor-pointer
          ${
            isDragOver
              ? "border-blue-500 bg-blue-50"
              : "border-gray-300 bg-white hover:border-gray-400"
          }
          ${uploading ? "pointer-events-none opacity-70" : ""}
        `}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          onChange={handleInputChange}
          className="hidden"
          aria-label="File upload"
        />

        {/* Upload icon */}
        <svg
          className="mb-3 h-10 w-10 text-gray-400"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={1.5}
            d="M12 16V4m0 0L8 8m4-4l4 4M4 14v4a2 2 0 002 2h12a2 2 0 002-2v-4"
          />
        </svg>

        <p className="text-sm text-gray-600">{label}</p>
        <p className="mt-1 text-xs text-gray-400">Accepted formats: {accept}</p>

        {selectedFile && (
          <p className="mt-3 text-sm font-medium text-gray-800">
            {selectedFile.name}
          </p>
        )}
      </div>

      {/* Progress bar */}
      {uploading && (
        <div className="mt-3">
          <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
            <div
              className="h-full rounded-full bg-blue-600 transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          <p className="mt-1 text-xs text-gray-500 text-center">
            Uploading… {progress}%
          </p>
        </div>
      )}

      {/* Success indicator */}
      {!uploading && progress === 100 && !error && (
        <p className="mt-2 text-sm text-green-600 text-center">
          ✓ Upload complete
        </p>
      )}

      {/* Error message */}
      {error && (
        <p className="mt-2 text-sm text-red-600 text-center">{error}</p>
      )}
    </div>
  );
}
