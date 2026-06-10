import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Router } from '@angular/router';
import {
  BehaviorSubject,
  Observable,
  catchError,
  filter,
  finalize,
  map,
  of,
  switchMap,
  take,
  tap
} from 'rxjs';

import { ApiService } from '../../core/api.service';

export interface AuthUser {
  id: number;
  email: string;
  full_name: string | null;
  role: string;
  status: 'pending' | 'active' | 'disabled';
  email_verified_at: string | null;
}

export interface AuthMessage {
  message: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly authenticatedSubject = new BehaviorSubject<boolean>(false);
  private readonly userSubject = new BehaviorSubject<AuthUser | null>(null);
  private readonly sessionRestoredSubject = new BehaviorSubject<boolean>(false);

  readonly authenticated$ = this.authenticatedSubject.asObservable();
  readonly user$ = this.userSubject.asObservable();

  constructor(
    private readonly http: HttpClient,
    private readonly api: ApiService,
    private readonly router: Router
  ) {
    window.addEventListener('skillmatch:unauthorized', () => {
      this.clearSession();
      void this.router.navigateByUrl('/login');
    });
    this.restoreSession().subscribe();
  }

  get isAuthenticated(): boolean {
    return this.authenticatedSubject.value;
  }

  waitForSession(): Observable<boolean> {
    return this.sessionRestoredSubject.pipe(
      filter((restored) => restored),
      take(1),
      map(() => this.authenticatedSubject.value)
    );
  }

  waitForUser(): Observable<AuthUser | null> {
    return this.sessionRestoredSubject.pipe(
      filter((restored) => restored),
      take(1),
      map(() => this.userSubject.value)
    );
  }

  login(email: string, password: string): Observable<AuthUser> {
    const body = new HttpParams()
      .set('username', email)
      .set('password', password);

    return this.sessionRestoredSubject.pipe(
      filter((restored) => restored),
      take(1),
      switchMap(() =>
        this.http.post<AuthUser>(`${this.api.baseUrl}/auth/login`, body)
      ),
      tap((user) => this.setAuthenticatedUser(user))
    );
  }

  register(email: string, password: string, fullName: string): Observable<AuthMessage> {
    return this.http
      .post<AuthMessage>(`${this.api.baseUrl}/auth/register`, {
        email,
        password,
        full_name: fullName
      });
  }

  verifyEmail(token: string): Observable<AuthMessage> {
    return this.http.post<AuthMessage>(`${this.api.baseUrl}/auth/verify-email`, {
      token
    }).pipe(
      switchMap((response) => {
        if (!this.isAuthenticated) {
          return of(response);
        }
        return this.refreshSession().pipe(map(() => response));
      })
    );
  }

  resendVerification(): Observable<AuthMessage> {
    return this.http.post<AuthMessage>(
      `${this.api.baseUrl}/auth/resend-verification`,
      {}
    );
  }

  refreshSession(): Observable<AuthUser | null> {
    return this.http.get<AuthUser>(`${this.api.baseUrl}/auth/session`).pipe(
      tap((user) => this.setAuthenticatedUser(user)),
      map((user) => user),
      catchError(() => of(null))
    );
  }

  loadCurrentUser(): Observable<AuthUser> {
    return this.http.get<AuthUser>(`${this.api.baseUrl}/auth/me`).pipe(
      tap((user) => this.userSubject.next(user))
    );
  }

  updateProfile(fullName: string): Observable<AuthUser> {
    return this.http.patch<AuthUser>(`${this.api.baseUrl}/auth/me`, {
      full_name: fullName
    }).pipe(
      tap((user) => this.userSubject.next(user))
    );
  }

  changePassword(currentPassword: string, newPassword: string): Observable<void> {
    return this.http.post<void>(`${this.api.baseUrl}/auth/change-password`, {
      current_password: currentPassword,
      new_password: newPassword
    });
  }

  logout(): void {
    this.http.post<void>(`${this.api.baseUrl}/auth/logout`, {}).pipe(
      finalize(() => {
        this.clearSession();
        void this.router.navigateByUrl('/login');
      })
    ).subscribe();
  }

  private restoreSession(): Observable<AuthUser | null> {
    return this.http.get<AuthUser>(`${this.api.baseUrl}/auth/session`).pipe(
      tap((user) => this.setAuthenticatedUser(user)),
      map((user) => user),
      catchError(() => {
        this.clearSession();
        return of(null);
      }),
      finalize(() => this.sessionRestoredSubject.next(true))
    );
  }

  private setAuthenticatedUser(user: AuthUser): void {
    this.userSubject.next(user);
    this.authenticatedSubject.next(true);
    this.sessionRestoredSubject.next(true);
  }

  private clearSession(): void {
    this.authenticatedSubject.next(false);
    this.userSubject.next(null);
  }
}
