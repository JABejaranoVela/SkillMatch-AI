import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, tap } from 'rxjs';

import { ApiService } from '../../core/api.service';

interface AuthToken {
  access_token: string;
  token_type: string;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly authenticatedSubject = new BehaviorSubject<boolean>(
    Boolean(localStorage.getItem('skillmatch_token'))
  );
  readonly authenticated$ = this.authenticatedSubject.asObservable();

  constructor(
    private readonly http: HttpClient,
    private readonly api: ApiService
  ) {}

  login(email: string, password: string): Observable<AuthToken> {
    const body = new HttpParams()
      .set('username', email)
      .set('password', password);

    return this.http.post<AuthToken>(`${this.api.baseUrl}/auth/login`, body).pipe(
      tap((token) => {
        localStorage.setItem('skillmatch_token', token.access_token);
        this.authenticatedSubject.next(true);
      })
    );
  }

  register(email: string, password: string, fullName: string): Observable<unknown> {
    return this.http.post(`${this.api.baseUrl}/auth/register`, {
      email,
      password,
      full_name: fullName
    });
  }

  logout(): void {
    localStorage.removeItem('skillmatch_token');
    this.authenticatedSubject.next(false);
  }
}
