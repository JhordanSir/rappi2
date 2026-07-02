/** Chequeo de permisos recurso:accion contra los permisos del rol (con comodín *).
 *  Función pura extraída de AuthContext para poder probarla de forma aislada. */

export interface PermisoLike {
  recurso: string;
  accion: string;
}

export function tienePermiso(permisos: PermisoLike[] | undefined, recurso: string, accion: string): boolean {
  return (permisos ?? []).some(
    (p) => (p.recurso === "*" || p.recurso === recurso) && (p.accion === "*" || p.accion === accion),
  );
}
