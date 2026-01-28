interface StatusToastProps {
  message: string
  tone?: 'success' | 'error'
}

export function StatusToast({ message, tone = 'success' }: StatusToastProps) {
  return <div className={`toast ${tone === 'error' ? 'toast-error' : 'toast-success'}`}>{message}</div>
}
