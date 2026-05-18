export default function LoadingSpinner() {
  return (
    <div className="flex items-center justify-center min-h-screen bg-[#080c1a]">
      <div role="status" aria-label="Loading" className="relative w-10 h-10">
        <div className="absolute inset-0 rounded-full border-2 border-white/[0.06]" />
        <div className="absolute inset-0 rounded-full border-2 border-transparent border-t-violet-500 border-r-cyan-400 animate-spin" />
      </div>
    </div>
  );
}
