import type { NavigateFunction } from "react-router-dom";
import { api } from "@/lib/api";
import type { CheckoutResponse } from "@/types";

/**
 * Inicia el pago de una orden y redirige según el proveedor: a MercadoPago
 * (URL externa) o a la pantalla de pago simulado interna.
 */
export async function iniciarCheckout(ordenId: number, navigate: NavigateFunction): Promise<void> {
  const { data } = await api.post<CheckoutResponse>(`/ordenes/${ordenId}/checkout`);
  if (data.proveedor === "mercadopago") {
    window.location.href = data.init_point;
  } else {
    navigate(`/pago/simulado?orden=${ordenId}`);
  }
}
