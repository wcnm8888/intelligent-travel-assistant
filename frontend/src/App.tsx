import { useEffect, useState } from "react";

import { fetchHealth, type HealthPayload } from "./health";
import "./styles.css";

type HealthState =
  | { phase: "loading" }
  | { phase: "success"; payload: HealthPayload }
  | { phase: "error" };

interface AppProps {
  checkHealth?: () => Promise<HealthPayload>;
}

export function App({ checkHealth = fetchHealth }: AppProps) {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<HealthState>({ phase: "loading" });

  useEffect(() => {
    let isCurrent = true;

    void checkHealth().then(
      (payload) => {
        if (isCurrent) setState({ phase: "success", payload });
      },
      () => {
        if (isCurrent) setState({ phase: "error" });
      },
    );

    return () => {
      isCurrent = false;
    };
  }, [attempt, checkHealth]);

  const isLoading = state.phase === "loading";
  const retry = () => {
    setState({ phase: "loading" });
    setAttempt((value) => value + 1);
  };

  return (
    <main className="shell">
      <div className="topographic-lines" aria-hidden="true" />

      <header className="masthead">
        <div className="wordmark">
          <span className="wordmark-mark" aria-hidden="true">
            行
          </span>
          <div>
            <p className="eyebrow">INTELLIGENT TRAVEL ASSISTANT</p>
            <p className="wordmark-title">本地旅行控制台</p>
          </div>
        </div>
        <span className="environment-badge">LOCAL · 仅本机</span>
      </header>

      <section className="hero" aria-labelledby="diagnostic-title">
        <div className="hero-copy">
          <p className="section-index">工程诊断 / 01</p>
          <h1 id="diagnostic-title">出发以前，先确认系统在线。</h1>
          <p className="hero-description">
            这里不会生成行程，也不会连接任何旅行数据服务。它只验证浏览器能否抵达本机
            FastAPI 服务。
          </p>
        </div>

        <div className="compass" aria-hidden="true">
          <span>N</span>
          <i />
        </div>
      </section>

      <section className="diagnostic-grid" aria-label="本地服务状态">
        <article className={`status-panel status-panel--${state.phase}`}>
          <div className="panel-heading">
            <div>
              <p className="panel-kicker">CONNECTION STATUS</p>
              <h2>本地 API</h2>
            </div>
            <span className="status-light" aria-hidden="true" />
          </div>

          <div className="status-message" aria-live="polite" aria-atomic="true">
            {state.phase === "loading" && (
              <div role="status">
                <p className="status-title">正在检查本地 API</p>
                <p>请求已发往 127.0.0.1，请稍候。</p>
              </div>
            )}

            {state.phase === "success" && (
              <div role="status">
                <p className="status-title">连接正常</p>
                <p>前端已就绪，后端健康响应有效。</p>
                <dl className="service-facts">
                  <div>
                    <dt>服务标识</dt>
                    <dd>{state.payload.service}</dd>
                  </div>
                  <div>
                    <dt>响应状态</dt>
                    <dd>{state.payload.status.toUpperCase()}</dd>
                  </div>
                </dl>
              </div>
            )}

            {state.phase === "error" && (
              <div role="alert">
                <p className="status-title">后端暂时无法连接</p>
                <p>请确认本地 FastAPI 已启动，然后重新检查。</p>
              </div>
            )}
          </div>

          <button
            className="check-button"
            type="button"
            disabled={isLoading}
            onClick={retry}
          >
            <span>{isLoading ? "检查进行中" : "重新检查"}</span>
            <span aria-hidden="true">→</span>
          </button>
        </article>

        <aside className="boundary-panel" aria-labelledby="boundary-title">
          <p className="panel-kicker">BOUNDARY NOTE</p>
          <h2 id="boundary-title">本页能证明什么</h2>
          <ul>
            <li>React 前端可以运行</li>
            <li>本机后端健康接口可达</li>
            <li>失败后可以由用户重试</li>
          </ul>
          <div className="boundary-warning">
            <span aria-hidden="true">!</span>
            <p>不代表天气、地图、模型或旅行规划能力已经可用。</p>
          </div>
        </aside>
      </section>

      <footer className="footer-note">
        <span>B-000 · PROJECT BASELINE</span>
        <span>数据请求范围：本机 /api/health</span>
      </footer>
    </main>
  );
}
