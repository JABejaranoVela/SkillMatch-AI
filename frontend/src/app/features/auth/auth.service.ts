import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Router } from '@angular/router';
import { BehaviorSubject, Observable, switchMap, tap } from 'rxjs';

import { ApiService } from '../../core/api.service';

interface AuthToken {
  access_token: string;
  token_type: string;
}

export interface AuthUser {
  id: number;
  email: string;
  full_name: string | null;
  role: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly authenticatedSubject = new BehaviorSubject<boolean>(this.hasToken());
  private readonly userSubject = new BehaviorSubject<AuthUser | null>(null);

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
    this.restoreSession();
  }

  get isAuthenticated(): boolean {
    return this.hasToken();
  }

  login(email: string, password: string): Observable<AuthUser> {
    const body = new HttpParams()
      .set('username', email)
      .set('password', password);

    return this.http.post<AuthToken>(`${this.api.baseUrl}/auth/login`, body).pipe(
      tap((token) => {
        localStorage.setItem('skillmatch_token', token.access_token);
        this.authenticatedSubject.next(true);
      }),
      switchMap(() => this.loadCurrentUser())
    );
  }

  register(email: string, password: string, fullName: string): Observable<AuthUser> {
    return this.http
      .post(`${this.api.baseUrl}/auth/register`, {
        email,
        password,
        full_name: fullName
      })
      .pipe(switchMap(() => this.login(email, password)));
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
    this.clearSession();
    void this.router.navigateByUrl('/login');
  }

  private restoreSession(): void {
    if (!this.hasToken()) {
      this.authenticatedSubject.next(false);
      return;
    }
    this.authenticatedSubject.next(true);
    this.loadCurrentUser().subscribe({
      error: () => this.clearSession()
    });
  }

  private clearSession(): void {
    localStorage.removeItem('skillmatch_token');
    this.authenticatedSubject.next(false);
    this.userSubject.next(null);
  }

  private hasToken(): boolean {
    return Boolean(localStorage.getItem('skillmatch_token'));
  }
}
