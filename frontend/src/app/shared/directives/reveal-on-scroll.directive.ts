import {
  Directive,
  ElementRef,
  Inject,
  NgZone,
  OnDestroy,
  OnInit,
  PLATFORM_ID
} from '@angular/core';
import { isPlatformBrowser } from '@angular/common';

@Directive({
  selector: '[appRevealOnScroll]',
  standalone: true
})
export class RevealOnScrollDirective implements OnInit, OnDestroy {
  private observer?: IntersectionObserver;

  constructor(
    private readonly elementRef: ElementRef<HTMLElement>,
    private readonly ngZone: NgZone,
    @Inject(PLATFORM_ID) private readonly platformId: object
  ) {}

  ngOnInit(): void {
    const element = this.elementRef.nativeElement;
    element.classList.add('reveal');

    if (!isPlatformBrowser(this.platformId)) {
      this.showElement();
      return;
    }

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      this.showElement();
      return;
    }

    if (!('IntersectionObserver' in window)) {
      this.showElement();
      return;
    }

    this.ngZone.runOutsideAngular(() => {
      this.observer = new IntersectionObserver(
        (entries) => {
          const entry = entries[0];
          if (!entry?.isIntersecting) {
            return;
          }
          this.showElement();
          this.observer?.disconnect();
          this.observer = undefined;
        },
        {
          rootMargin: '0px 0px -10% 0px',
          threshold: 0.12
        }
      );
      this.observer.observe(element);
    });
  }

  ngOnDestroy(): void {
    this.observer?.disconnect();
  }

  private showElement(): void {
    this.elementRef.nativeElement.classList.add('reveal-visible');
  }
}
