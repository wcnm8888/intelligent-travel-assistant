import { useEffect, useRef, useState } from "react";

interface TerminalTaskActionsProps {
  onDelete: () => Promise<void>;
}

export function TerminalTaskActions({ onDelete }: TerminalTaskActionsProps) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (confirming) confirmRef.current?.focus();
  }, [confirming]);

  const cancel = () => {
    if (deleting) return;
    setConfirming(false);
    setError(null);
    window.setTimeout(() => triggerRef.current?.focus(), 0);
  };

  const remove = async () => {
    setDeleting(true);
    setError(null);
    try {
      await onDelete();
    } catch {
      setDeleting(false);
      setError("无法删除本机任务，请稍后重试。");
    }
  };

  return (
    <div className="terminal-task-actions">
      <button
        className="terminal-delete-trigger"
        type="button"
        ref={triggerRef}
        hidden={confirming}
        onClick={() => setConfirming(true)}
      >
        删除本机任务
      </button>
      {confirming && (
        <div
          className="terminal-delete-confirmation"
          role="alertdialog"
          aria-labelledby="terminal-delete-title"
          aria-describedby="terminal-delete-description"
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              event.preventDefault();
              cancel();
            }
          }}
        >
          <strong id="terminal-delete-title">确认删除这一个本机任务？</strong>
          <p id="terminal-delete-description">
            删除后无法从本机恢复，但不会删除其他任务。
          </p>
          <div className="terminal-delete-controls">
            <button
              type="button"
              ref={confirmRef}
              disabled={deleting}
              onClick={() => void remove()}
            >
              {deleting ? "正在删除" : "确认删除"}
            </button>
            <button type="button" disabled={deleting} onClick={cancel}>
              取消
            </button>
          </div>
          {error && <p role="alert">{error}</p>}
        </div>
      )}
    </div>
  );
}
