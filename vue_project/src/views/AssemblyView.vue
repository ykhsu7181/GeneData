<template>
  <div class="assembly-page">
    <section class="assembly-placeholder" aria-labelledby="assembly-title">
      <span class="assembly-mark" aria-hidden="true">
        <svg viewBox="0 0 52 52">
          <rect x="8" y="10" width="36" height="32" rx="8"></rect>
          <path d="M16 19h20M16 26h20M16 33h13"></path>
        </svg>
      </span>
      <p class="eyebrow">ASSEMBLY</p>
      <h1 id="assembly-title">Assembly</h1>
      <p>Assembly resources and related functions are currently under development.</p>
      <span class="coming-soon">Coming soon</span>
    </section>
  </div>
</template>

<script>
export default {
  name: 'AssemblyView'
}
</script>

<style scoped>
.assembly-page {
  min-height: 520px;
  display: grid;
  place-items: center;
}

.assembly-placeholder {
  width: min(660px, 100%);
  padding: 64px 36px;
  border: 1px solid #dbe7f3;
  border-radius: 22px;
  background:
    radial-gradient(circle at 50% 0, rgba(22, 119, 232, 0.1), transparent 46%),
    #ffffff;
  box-shadow: 0 18px 44px rgba(22, 55, 94, 0.08);
  text-align: center;
}

.assembly-mark {
  width: 58px;
  height: 58px;
  margin: 0 auto 20px;
  display: grid;
  place-items: center;
  border-radius: 16px;
  color: #176fd6;
  background: #eaf4ff;
}

.assembly-mark svg {
  width: 42px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
}

.eyebrow {
  margin: 0 0 8px;
  color: #1677e8;
  font-size: 0.75rem;
  font-weight: 800;
  letter-spacing: 0.18em;
}

h1 {
  margin: 0;
  color: #0c2346;
  font-size: clamp(2.2rem, 5vw, 3.2rem);
}

.assembly-placeholder > p:not(.eyebrow) {
  max-width: 480px;
  margin: 16px auto 0;
  color: #617792;
  font-size: 1rem;
  line-height: 1.7;
}

.coming-soon {
  display: inline-flex;
  margin-top: 24px;
  padding: 8px 14px;
  border-radius: 999px;
  color: #315f92;
  background: #f0f6fc;
  font-size: 0.82rem;
  font-weight: 700;
}

@media (max-width: 620px) {
  .assembly-page { min-height: 440px; }
  .assembly-placeholder { padding: 48px 22px; }
}
</style>
