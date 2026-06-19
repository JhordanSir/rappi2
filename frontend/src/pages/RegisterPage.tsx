import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { Package } from "lucide-react";
import toast from "react-hot-toast";
import { useAuth } from "@/auth/AuthContext";
import { api, apiError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";

/** Registro público de clientes. Crea la cuenta (siempre rol Cliente) y entra. */
export default function RegisterPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ nombre: "", username: "", email: "", password: "", telefono: "" });
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post("/auth/register", form);
      await login(form.username, form.password);
      toast.success("¡Cuenta creada! Bienvenido");
      navigate("/");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-sillar-100 px-6 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-600 text-white shadow-card">
            <Package className="h-6 w-6" />
          </div>
          <div>
            <p className="text-lg font-bold text-stone-900">Rappi2</p>
            <p className="-mt-1 text-sm text-stone-500">Crea tu cuenta de cliente</p>
          </div>
        </div>
        <form onSubmit={submit} className="space-y-4 rounded-2xl border border-sillar-300 bg-white p-6 shadow-soft">
          <Field label="Nombre" required>
            <Input value={form.nombre} onChange={set("nombre")} placeholder="Tu nombre" autoFocus />
          </Field>
          <Field label="Usuario" required>
            <Input value={form.username} onChange={set("username")} placeholder="usuario" />
          </Field>
          <Field label="Email" required>
            <Input type="email" value={form.email} onChange={set("email")} placeholder="tu@correo.com" />
          </Field>
          <Field label="Teléfono">
            <Input value={form.telefono} onChange={set("telefono")} placeholder="9XXXXXXXX" />
          </Field>
          <Field label="Contraseña" required>
            <Input type="password" value={form.password} onChange={set("password")} placeholder="••••••••" />
          </Field>
          <Button type="submit" loading={loading} size="lg" className="w-full">
            Crear cuenta
          </Button>
          <p className="text-center text-sm text-stone-500">
            ¿Ya tienes cuenta?{" "}
            <Link to="/login" className="font-semibold text-brand-700 hover:underline">
              Inicia sesión
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
