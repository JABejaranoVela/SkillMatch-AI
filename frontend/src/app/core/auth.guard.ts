import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map } from 'rxjs';

import { AuthService, AuthUser } from '../features/auth/auth.service';

export function isVerifiedUser(user: AuthUser | null): boolean {
  return user?.status === 'active' && user.email_verified_at !== null;
}

export const verifiedGuard: CanActivateFn = (_route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.waitForUser().pipe(
    map((user) => {
      if (isVerifiedUser(user)) {
        return true;
      }
      if (user?.status === 'pending') {
        return router.createUrlTree(['/verify-email-sent']);
      }
      return router.createUrlTree(['/login'], {
        queryParams: { returnUrl: state.url }
      });
    })
  );
};

export const authGuard = verifiedGuard;

export const sessionGuard: CanActivateFn = (_route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.waitForSession().pipe(
    map((isAuthenticated) => {
      if (isAuthenticated) {
        return true;
      }
      return router.createUrlTree(['/login'], {
        queryParams: { returnUrl: state.url }
      });
    })
  );
};

export const pendingGuard: CanActivateFn = (_route, state) => {
  const authService = inject(AuthService);
  const router = inject(Router);

  return authService.waitForUser().pipe(
    map((user) => {
      if (user === null) {
        return true;
      }
      if (user?.status === 'pending') {
        return true;
      }
      if (isVerifiedUser(user)) {
        return router.createUrlTree(['/resumes']);
      }
      return router.createUrlTree(['/login'], {
        queryParams: { returnUrl: state.url }
      });
    })
  );
};
