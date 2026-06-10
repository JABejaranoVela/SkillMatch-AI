import { AsyncPipe } from '@angular/common';
import { Component, HostListener, OnDestroy } from '@angular/core';
import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
  RouterOutlet
} from '@angular/router';
import { filter, Subscription } from 'rxjs';
import {
  LucideBookmark,
  LucideChevronDown,
  LucideFileUser,
  LucideHouse,
  LucideLogIn,
  LucideLogOut,
  LucideMenu,
  LucideSearch,
  LucideSettings,
  LucideUserPlus,
  LucideUserRound,
  LucideX
} from '@lucide/angular';

import { AuthService, AuthUser } from './features/auth/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    AsyncPipe,
    RouterLink,
    RouterLinkActive,
    RouterOutlet,
    LucideBookmark,
    LucideChevronDown,
    LucideFileUser,
    LucideHouse,
    LucideLogIn,
    LucideLogOut,
    LucideMenu,
    LucideSearch,
    LucideSettings,
    LucideUserPlus,
    LucideUserRound,
    LucideX
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss'
})
export class AppComponent implements OnDestroy {
  readonly authenticated$ = this.authService.authenticated$;
  readonly user$ = this.authService.user$;
  sidebarOpen = false;
  userMenuOpen = false;
  publicLayout = this.isPublicRoute(this.router.url);

  private readonly navigationSubscription: Subscription;

  constructor(
    private readonly authService: AuthService,
    private readonly router: Router
  ) {
    this.navigationSubscription = this.router.events
      .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
      .subscribe((event) => {
        this.publicLayout = this.isPublicRoute(event.urlAfterRedirects);
        this.closeSidebar();
        this.userMenuOpen = false;
      });
  }

  ngOnDestroy(): void {
    this.navigationSubscription.unsubscribe();
    document.body.style.overflow = '';
  }

  @HostListener('document:keydown.escape')
  closeMenus(): void {
    this.closeSidebar();
    this.userMenuOpen = false;
  }

  @HostListener('document:click', ['$event'])
  closeUserMenuOnOutsideClick(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    if (!target.closest('.user-menu')) {
      this.userMenuOpen = false;
    }
  }

  toggleSidebar(): void {
    this.sidebarOpen = !this.sidebarOpen;
    document.body.style.overflow = this.sidebarOpen ? 'hidden' : '';
  }

  closeSidebar(): void {
    this.sidebarOpen = false;
    document.body.style.overflow = '';
  }

  toggleUserMenu(event: MouseEvent): void {
    event.stopPropagation();
    this.userMenuOpen = !this.userMenuOpen;
  }

  initials(user: AuthUser | null): string {
    const source = user?.full_name?.trim() || user?.email || 'Usuario';
    return source
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join('')
      .toUpperCase();
  }

  displayName(user: AuthUser | null): string {
    return user?.full_name?.trim() || user?.email.split('@')[0] || 'Usuario';
  }

  logout(): void {
    this.userMenuOpen = false;
    this.closeSidebar();
    this.authService.logout();
  }

  private isPublicRoute(url: string): boolean {
    const path = url.split(/[?#]/, 1)[0];
    return (
      path === '/' ||
      path === '/login' ||
      path === '/register' ||
      path === '/verify-email' ||
      path === '/verify-email-sent'
    );
  }
}
