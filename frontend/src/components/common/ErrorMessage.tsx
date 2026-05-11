interface Props {
  message: string;
}

export default function ErrorMessage({ message }: Props) {
  return (
    <div role="alert" className="rounded-lg bg-red-50 border border-red-200 p-4 text-sm text-red-700">
      {message}
    </div>
  );
}
