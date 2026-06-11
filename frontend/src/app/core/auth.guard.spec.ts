import { TestBed } from '@angular/core/testing';
import {
  ActivatedRouteSnapshot,
  Router,
  RouterStateSnapshot,
  UrlTree,
  provideRouter
} from '@angular/router';
import { firstValueFrom, Observable, of } from 'rxjs';

import { AuthService, AuthUser } from '../features/auth/auth.service';
import { verifiedGuard } from './auth.guard';

function user(
  status: AuthUser['status'],
  emailVerifiedAt: string | null
): AuthUser {
  return {
    id: 1,
    email: 'user@example.com',
    full_name: 'Test User',
    role: 'user',
    status,
    email_verified_at: emailVerifiedAt
  };
}

async function runGuard(
  authUser: AuthUser | null,
  accountStateReason: 'disabled' | null = null
): Promise<boolean | UrlTree> {
  TestBed.configureTestingModule({
    providers: [
      provideRouter([]),
      {
        provide: AuthService,
        useValue: {
          waitForUser: () => of(authUser),
          currentAccountStateReason: accountStateReason
        }
      }
    ]
  });

  const result = TestBed.runInInjectionContext(() =>
    verifiedGuard(
      {} as ActivatedRouteSnapshot,
      { url: '/jobs' } as RouterStateSnapshot
    )
  );
  return firstValueFrom(result as Observable<boolean | UrlTree>);
}

describe('verifiedGuard', () => {
  afterEach(() => TestBed.resetTestingModule());

  it('allows active users with a verified email', async () => {
    expect(await runGuard(user('active', '2026-06-10T12:00:00Z'))).toBeTrue();
  });

  it('redirects pending users to the verification screen', async () => {
    const result = await runGuard(user('pending', null));
    const router = TestBed.inject(Router);

    expect(router.serializeUrl(result as UrlTree)).toBe('/verify-email-sent');
  });

  it('does not trust active status without email verification', async () => {
    const result = await runGuard(user('active', null));
    const router = TestBed.inject(Router);

    expect(router.serializeUrl(result as UrlTree)).toBe('/login?returnUrl=%2Fjobs');
  });

  it('redirects disabled users to login with a specific reason', async () => {
    const result = await runGuard(user('disabled', '2026-06-10T12:00:00Z'));
    const router = TestBed.inject(Router);

    expect(router.serializeUrl(result as UrlTree)).toBe('/login?reason=disabled');
  });

  it('preserves the disabled reason when session restoration returns no user', async () => {
    const result = await runGuard(null, 'disabled');
    const router = TestBed.inject(Router);

    expect(router.serializeUrl(result as UrlTree)).toBe('/login?reason=disabled');
  });
});
