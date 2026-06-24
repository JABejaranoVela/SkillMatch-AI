import { Component } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { RevealOnScrollDirective } from './reveal-on-scroll.directive';

@Component({
  standalone: true,
  imports: [RevealOnScrollDirective],
  template: '<section appRevealOnScroll>Contenido</section>'
})
class HostComponent {}

describe('RevealOnScrollDirective', () => {
  let originalIntersectionObserver: typeof IntersectionObserver | undefined;
  let originalMatchMedia: typeof window.matchMedia;
  let observeSpy: jasmine.Spy;
  let disconnectSpy: jasmine.Spy;
  let observerCallback: IntersectionObserverCallback;

  function mockMotionPreference(reduce = false): void {
    spyOn(window, 'matchMedia').and.returnValue({
      matches: reduce,
      media: '(prefers-reduced-motion: reduce)',
      onchange: null,
      addListener: jasmine.createSpy('addListener'),
      removeListener: jasmine.createSpy('removeListener'),
      addEventListener: jasmine.createSpy('addEventListener'),
      removeEventListener: jasmine.createSpy('removeEventListener'),
      dispatchEvent: jasmine.createSpy('dispatchEvent')
    } as unknown as MediaQueryList);
  }

  function mockIntersectionObserver(): void {
    observeSpy = jasmine.createSpy('observe');
    disconnectSpy = jasmine.createSpy('disconnect');

    class MockIntersectionObserver {
      constructor(callback: IntersectionObserverCallback) {
        observerCallback = callback;
      }

      observe = observeSpy;
      disconnect = disconnectSpy;
      unobserve = jasmine.createSpy('unobserve');
      takeRecords = jasmine.createSpy('takeRecords').and.returnValue([]);
      root = null;
      rootMargin = '0px';
      thresholds = [0];
    }

    window.IntersectionObserver =
      MockIntersectionObserver as unknown as typeof IntersectionObserver;
  }

  async function createFixture(): Promise<ComponentFixture<HostComponent>> {
    await TestBed.configureTestingModule({
      imports: [HostComponent]
    }).compileComponents();

    const fixture = TestBed.createComponent(HostComponent);
    fixture.detectChanges();
    return fixture;
  }

  beforeEach(() => {
    originalIntersectionObserver = window.IntersectionObserver;
    originalMatchMedia = window.matchMedia;
  });

  afterEach(() => {
    if (originalIntersectionObserver) {
      window.IntersectionObserver = originalIntersectionObserver;
    } else {
      delete (window as unknown as { IntersectionObserver?: typeof IntersectionObserver })
        .IntersectionObserver;
    }
    window.matchMedia = originalMatchMedia;
    TestBed.resetTestingModule();
  });

  it('creates an observer when motion is allowed', async () => {
    mockMotionPreference(false);
    mockIntersectionObserver();

    const fixture = await createFixture();
    const element = fixture.nativeElement.querySelector('section') as HTMLElement;

    expect(element.classList).toContain('reveal');
    expect(observeSpy).toHaveBeenCalledWith(element);
  });

  it('marks the element visible once it enters the viewport and disconnects', async () => {
    mockMotionPreference(false);
    mockIntersectionObserver();

    const fixture = await createFixture();
    const element = fixture.nativeElement.querySelector('section') as HTMLElement;
    observerCallback([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver);

    expect(element.classList).toContain('reveal-visible');
    expect(disconnectSpy).toHaveBeenCalled();
  });

  it('disconnects the observer on destroy', async () => {
    mockMotionPreference(false);
    mockIntersectionObserver();

    const fixture = await createFixture();
    fixture.destroy();

    expect(disconnectSpy).toHaveBeenCalled();
  });

  it('shows content directly when reduced motion is enabled', async () => {
    mockMotionPreference(true);
    mockIntersectionObserver();

    const fixture = await createFixture();
    const element = fixture.nativeElement.querySelector('section') as HTMLElement;

    expect(element.classList).toContain('reveal-visible');
    expect(observeSpy).not.toHaveBeenCalled();
  });

  it('shows content directly if IntersectionObserver is unavailable', async () => {
    mockMotionPreference(false);
    delete (window as unknown as { IntersectionObserver?: typeof IntersectionObserver })
      .IntersectionObserver;

    const fixture = await createFixture();
    const element = fixture.nativeElement.querySelector('section') as HTMLElement;

    expect(element.classList).toContain('reveal-visible');
  });
});
