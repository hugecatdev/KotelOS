local rows, cols = io.popen("stty size"):read("n", "n")
rows, cols = (rows or 24) - 2, cols or 80
math.randomseed(os.time())

local g = {}
for y = 1, rows do
  g[y] = {}
  for x = 1, cols do g[y][x] = math.random() < 0.25 end
end

local function alive(y, x)
  local r = g[(y - 1) % rows + 1]
  return r[(x - 1) % cols + 1] and 1 or 0
end

io.write("\27[2J")
for gen = 1, 100 do
  local out, n = {}, {}
  for y = 1, rows do
    local line = {}
    n[y] = {}
    for x = 1, cols do
      local s = alive(y - 1, x - 1) + alive(y - 1, x) + alive(y - 1, x + 1) + alive(y, x - 1)
        + alive(y, x + 1) + alive(y + 1, x - 1) + alive(y + 1, x) + alive(y + 1, x + 1)
      n[y][x] = s == 3 or (s == 2 and g[y][x])
      line[x] = g[y][x] and "#" or " "
    end
    out[y] = table.concat(line)
  end
  io.write("\27[H", table.concat(out, "\n"), "\n generation ", gen, "   Ctrl+C - stop")
  io.flush()
  g = n
end
io.write("\n")
