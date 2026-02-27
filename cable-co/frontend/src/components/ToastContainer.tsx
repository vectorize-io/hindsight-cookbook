import type { Toast } from '../hooks/useToast.ts';

const typeStyles = {
  error: 'bg-red-900/90 border-red-500 text-red-100',
  success: 'bg-green-900/90 border-green-500 text-green-100',
  info: 'bg-blue-900/90 border-blue-500 text-blue-100',
};

const typeIcons = {
  error: '\u2715',
  success: '\u2713',
  info: '\u2139',
};

export function ToastContainer({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {toasts.map(toast => (
        <div
          key={toast.id}
          className={`flex items-start gap-2 px-4 py-3 rounded-lg border shadow-lg text-sm cursor-pointer ${typeStyles[toast.type]}`}
          onClick={() => onDismiss(toast.id)}
          role="alert"
        >
          <span className="font-bold mt-0.5">{typeIcons[toast.type]}</span>
          <span className="flex-1">{toast.message}</span>
        </div>
      ))}
    </div>
  );
}
