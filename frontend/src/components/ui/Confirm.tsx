import { Modal } from "./Modal";
import { Button } from "./Button";

export function ConfirmModal({
  open,
  title = "¿Confirmar acción?",
  description,
  confirmLabel = "Confirmar",
  danger,
  loading,
  onConfirm,
  onClose,
}: {
  open: boolean;
  title?: string;
  description?: string;
  confirmLabel?: string;
  danger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onClose: () => void;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      size="sm"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button variant={danger ? "danger" : "primary"} loading={loading} onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <p className="text-sm text-slate-600">{description}</p>
    </Modal>
  );
}
