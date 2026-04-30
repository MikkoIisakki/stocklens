export function ErrorPanel({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="rounded border border-red-200 bg-red-50 p-4 text-sm text-red-900">
      <p className="font-semibold">{title}</p>
      {detail ? <p className="mt-1 text-red-700">{detail}</p> : null}
    </div>
  );
}
