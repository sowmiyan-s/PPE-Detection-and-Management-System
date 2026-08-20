import React from "react";
import { AlertTriangle, X, Trash2, Check, Loader2 } from "lucide-react";

type ConfirmModalProps = {
  isOpen: boolean;
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  variant?: "danger" | "warning" | "info";
  isLoading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmModal({
  isOpen,
  title,
  message,
  confirmText = "Confirm",
  cancelText = "Cancel",
  variant = "danger",
  isLoading = false,
  onConfirm,
  onCancel,
}: ConfirmModalProps) {
  if (!isOpen) return null;

  const isDanger = variant === "danger";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4 animate-in fade-in duration-200">
      <div className="relative w-full max-w-md overflow-hidden rounded-lg border border-border panel-surface shadow-2xl">
        {/* Hazard Stripe Top Line */}
        <div
          className={`h-1.5 w-full ${
            isDanger ? "bg-gradient-to-r from-red-600 via-amber-500 to-red-600" : "bg-primary"
          }`}
        />

        {/* Modal Header */}
        <div className="flex items-center justify-between border-b border-border/80 px-5 py-4 bg-background/50">
          <div className="flex items-center gap-2.5">
            <div
              className={`rounded-full p-2 ${
                isDanger
                  ? "bg-destructive/15 text-destructive border border-destructive/30"
                  : "bg-primary/15 text-primary border border-primary/30"
              }`}
            >
              <AlertTriangle className="size-5" />
            </div>
            <h3 className="display-title text-base font-bold text-foreground">{title}</h3>
          </div>
          <button
            onClick={onCancel}
            disabled={isLoading}
            className="rounded p-1 text-muted-foreground hover:bg-accent hover:text-foreground transition-colors disabled:opacity-50"
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="px-5 py-4">
          <p className="text-sm text-muted-foreground leading-relaxed">{message}</p>
        </div>

        {/* Modal Footer / Actions */}
        <div className="flex items-center justify-end gap-2.5 border-t border-border/80 bg-background/40 px-5 py-3.5">
          <button
            type="button"
            onClick={onCancel}
            disabled={isLoading}
            className="rounded border border-border bg-background/80 px-4 py-2 text-xs font-medium text-foreground hover:bg-accent transition-colors disabled:opacity-50 cursor-pointer"
          >
            {cancelText}
          </button>

          <button
            type="button"
            onClick={onConfirm}
            disabled={isLoading}
            className={`flex items-center gap-1.5 rounded px-4 py-2 text-xs font-bold transition-all cursor-pointer disabled:opacity-50 ${
              isDanger
                ? "bg-destructive text-destructive-foreground hover:bg-destructive/90 shadow-md shadow-destructive/20"
                : "bg-primary text-primary-foreground hover:bg-primary/90 shadow-md shadow-primary/20"
            }`}
          >
            {isLoading ? (
              <Loader2 className="size-3.5 animate-spin" />
            ) : isDanger ? (
              <Trash2 className="size-3.5" />
            ) : (
              <Check className="size-3.5" />
            )}
            <span>{confirmText}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
