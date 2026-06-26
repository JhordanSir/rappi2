import { GoogleLogin } from "@react-oauth/google";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { useAuth } from "@/auth/AuthContext";
import { apiError } from "@/lib/api";

// Si no hay client ID configurado, el botón no se renderiza.
const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";

/** Botón "Continuar con Google" (Google Identity Services). Verifica el ID token
 *  contra el backend (/auth/google) y enruta al usuario tras autenticarse. */
export function GoogleSignInButton() {
  const { loginWithGoogle } = useAuth();
  const navigate = useNavigate();

  if (!GOOGLE_CLIENT_ID) return null;

  const onSuccess = async (credential?: string) => {
    if (!credential) {
      toast.error("No se recibió la credencial de Google");
      return;
    }
    try {
      await loginWithGoogle(credential);
      toast.success("Bienvenido");
      navigate("/");
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  return (
    <div className="mt-6">
      <div className="mb-4 flex items-center gap-3">
        <span className="h-px flex-1 bg-sillar-300" />
        <span className="text-xs uppercase tracking-wide text-stone-400">o</span>
        <span className="h-px flex-1 bg-sillar-300" />
      </div>
      <div className="flex justify-center">
        <GoogleLogin
          onSuccess={(resp) => onSuccess(resp.credential)}
          onError={() => toast.error("No se pudo iniciar sesión con Google")}
          theme="outline"
          size="large"
          text="continue_with"
          shape="rectangular"
        />
      </div>
    </div>
  );
}
