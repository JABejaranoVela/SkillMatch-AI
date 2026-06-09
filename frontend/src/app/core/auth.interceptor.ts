import { HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const token = localStorage.getItem('skillmatch_token');
  if (!token) {
    return next(request);
  }

  return next(request.clone({
    setHeaders: {
      Authorization: `Bearer ${token}`
    }
  })).pipe(
    catchError((error) => {
      if (error.status === 401) {
        localStorage.removeItem('skillmatch_token');
        window.dispatchEvent(new Event('skillmatch:unauthorized'));
      }
      return throwError(() => error);
    })
  );
};
