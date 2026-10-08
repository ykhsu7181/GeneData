import net from 'node:net'

const options = Object.fromEntries(
  process.argv.slice(2).map(argument => {
    const [key, ...value] = argument.replace(/^--/, '').split('=')
    return [key, value.join('=')]
  }),
)

const listenAddress = options['listen-address']
const listenPort = Number(options['listen-port'] || 13306)
const targetAddress = options['target-address'] || '127.0.0.1'
const targetPort = Number(options['target-port'] || 3306)

if (!listenAddress || !Number.isInteger(listenPort) || !Number.isInteger(targetPort)) {
  console.error(
    'Usage: node dev_mysql_bridge.mjs --listen-address=ADDRESS ' +
      '[--listen-port=13306] [--target-address=127.0.0.1] [--target-port=3306]',
  )
  process.exit(2)
}

const server = net.createServer(client => {
  const upstream = net.connect(targetPort, targetAddress)
  const close = () => {
    client.destroy()
    upstream.destroy()
  }
  client.pipe(upstream)
  upstream.pipe(client)
  client.on('error', close)
  upstream.on('error', close)
})

server.on('error', error => {
  console.error(error.message)
  process.exitCode = 1
})

server.listen(listenPort, listenAddress, () => {
  console.log(
    `MySQL development bridge listening on ${listenAddress}:${listenPort} ` +
      `and forwarding to ${targetAddress}:${targetPort}`,
  )
})

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => server.close(() => process.exit(0)))
}
