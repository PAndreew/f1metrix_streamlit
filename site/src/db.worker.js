import initSqlJs from 'sql.js';
let database;
const columns = {rank:'rank',name:'name',skill:'skill',races:'races',last_year:'last_year'};
self.onmessage = async ({data}) => {
  try {
    if (!database) {
      const SQL = await initSqlJs({locateFile: () => '/sql-wasm.wasm'});
      const response = await fetch('/data/rankings.sqlite');
      if (!response.ok) throw new Error('Database unavailable');
      database = new SQL.Database(new Uint8Array(await response.arrayBuffer()));
    }
    const q = '%' + String(data.search || '').slice(0,100) + '%';
    const minimum = Math.max(0, Math.min(2000, Number(data.minimum) || 0));
    const where = 'WHERE (name LIKE ? OR nationality LIKE ?) AND races >= ?' + (data.active ? ' AND last_year >= ?' : '');
    const params = [q,q,minimum,...(data.active ? [data.year] : [])];
    const count = database.prepare('SELECT count(*) AS total FROM drivers ' + where);
    count.bind(params); count.step(); const total = count.getAsObject().total; count.free();
    const sort = columns[data.sort] || 'rank';
    const direction = data.direction === 'desc' ? 'DESC' : 'ASC';
    const stmt = database.prepare(`SELECT * FROM drivers ${where} ORDER BY ${sort} ${direction}, id ASC LIMIT 25 OFFSET ?`);
    stmt.bind([...params,Math.max(0,Number(data.page)||0)*25]);
    const rows=[]; while(stmt.step()) rows.push(stmt.getAsObject()); stmt.free();
    self.postMessage({id:data.id,rows,total});
  } catch (error) { self.postMessage({id:data.id,error:String(error)}); }
};
