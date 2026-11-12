import React from 'react';
import { AlertTriangle, Loader2 } from 'lucide-react';
import { Modal } from './Modal';

interface ConfirmModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  isLoading?: boolean;
  variant?: 'danger' | 'primary';
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  isLoading = false,
  variant = 'danger',
}) => {
  return (
    <Modal isOpen={isOpen} onClose={isLoading ? () => undefined : onClose} title={title} size="sm">
      <div className="flex items-start gap-3">
        <div
          className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${
            variant === 'danger'
              ? 'bg-red-100 text-red-600 dark:bg-red-950/50 dark:text-red-400'
              : 'bg-indigo-100 text-indigo-600 dark:bg-indigo-950/50 dark:text-indigo-400'
          }`}
        >
          <AlertTriangle className="h-4 w-4" />
        </div>
        <p className="text-sm leading-relaxed text-app-text-secondary">{message}</p>
      </div>
      <div className="mt-5 flex items-center justify-end gap-2.5 border-t border-app-border pt-4">
        <button
          type="button"
          onClick={onClose}
          disabled={isLoading}
          className="btn-secondary"
        >
          {cancelLabel}
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={isLoading}
          className={variant === 'danger' ? 'btn-danger' : 'btn-primary'}
        >
          {isLoading && <Loader2 className="h-4 w-4 animate-spin" />}
          {confirmLabel}
        </button>
      </div>
    </Modal>
  );
};

