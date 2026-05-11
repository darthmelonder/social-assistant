export default function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center min-h-screen">
      <div
        role="status"
        aria-label="Loading"
        className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"
      />
    </div>
  );
}
