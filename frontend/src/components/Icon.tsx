interface IconProps {
  readonly name:
    | "plus"
    | "inbox"
    | "send"
    | "target"
    | "connection"
    | "arrow"
    | "back"
    | "close"
    | "refresh"
    | "logout"
    | "check"
    | "clock"
    | "alert"
    | "key"
    | "sun"
    | "moon";
  readonly size?: number;
}

const paths = {
  plus: "M12 5v14M5 12h14",
  inbox: "M4 4h16v16H4zM4 13h5l2 3h2l2-3h5",
  send: "m4 4 17 8-17 8V4Zm0 8h17",
  target: "M4 5h10v10H4zM10 15v5h10V10h-6",
  connection: "M8 7V4h8v3M5 10h14v10H5zM9 10V7h6v3",
  arrow: "M4 12h16m-6-6 6 6-6 6",
  back: "M20 12H4m6-6-6 6 6 6",
  close: "m6 6 12 12M18 6 6 18",
  refresh: "M20 8a8 8 0 1 0 0 8M20 3v5h-5",
  logout: "M9 4H4v16h5m6-13 5 5-5 5m-6-5h11",
  check: "m5 12 4 4L19 6",
  clock: "M12 8v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0",
  alert: "m12 3 10 18H2L12 3Zm0 6v5m0 3v.1",
  key: "M14 10a5 5 0 1 1-4-5 5 5 0 0 1 4 5Zm0 0h7v4h-3v3h-4v-7Z",
  sun: "M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0",
  moon: "M20 15A8 8 0 0 1 9 4a8 8 0 1 0 11 11Z",
};

export function Icon({ name, size = 18 }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name]} />
    </svg>
  );
}

export function HeraldMark() {
  return (
    <svg
      className="herald-mark"
      width="30"
      height="26"
      viewBox="0 0 30 26"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2 5h18m-4-4 5 4-5 4M5 13h20m-4-4 5 4-5 4M2 21h25m-4-4 5 4-5 4" />
    </svg>
  );
}
