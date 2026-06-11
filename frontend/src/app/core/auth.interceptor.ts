import { HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const requestWithCredentials = request.clone({ withCredentials: true });
  const handlesAccountError =
    request.url.endsWith('/auth/login') ||
    request.url.endsWith('/auth/register') ||
    request.url.endsWith('/auth/forgot-password') ||
    request.url.endsWith('/auth/reset-password') ||
    request.url.endsWith('/auth/session');

  return next(requestWithCredentials).pipe(
    catchError((error) => {
      if (!handlesAccountError && error.status === 401) {
        window.dispatchEvent(new CustomEvent('skillmatch:account-state', {
          detail: {
            reason: 'expired',
            returnUrl: `${window.location.pathname}${window.location.search}`
          }
        }));
      }
      const detail = String(error?.error?.detail || '').toLowerCase();
      if (!handlesAccountError && error.status === 403 && detail.includes('deshabilitada')) {
        window.dispatchEvent(new CustomEvent('skillmatch:account-state', {
          detail: { reason: 'disabled' }
        }));
      }
      return throwError(() => error);
    })
  );
};
