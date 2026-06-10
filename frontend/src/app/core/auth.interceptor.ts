import { HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const requestWithCredentials = request.clone({ withCredentials: true });
  const handlesExpectedUnauthorized =
    request.url.endsWith('/auth/login') ||
    request.url.endsWith('/auth/register') ||
    request.url.endsWith('/auth/session');

  return next(requestWithCredentials).pipe(
    catchError((error) => {
      if (error.status === 401 && !handlesExpectedUnauthorized) {
        window.dispatchEvent(new Event('skillmatch:unauthorized'));
      }
      return throwError(() => error);
    })
  );
};
