export {};

declare global {
  interface Window {
    /** Present only when running inside the Hearth Electron desktop shell. */
    hearth?: {
      isDesktop: boolean;
      chooseDataDir(): Promise<{ path: string } | null>;
      openDataDir?(): Promise<void>;
    };
  }
}
