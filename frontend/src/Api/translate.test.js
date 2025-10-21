import translate from './translate'

test('no filter and default config', () => {
  const query = translate([])
  expect(query).toEqual({ limit: 50 })
})

test('no pagination', () => {
  const query = translate([{ limit: 0 }])
  expect(query).toEqual({ limit: 0 })
})

test('custom ordering', () => {
  const query = translate([
    {
      order: ['foo ASC', 'bar DESC'],
    },
  ])

  expect(query).toEqual({ order: ['foo ASC', 'bar DESC'], limit: 50 })
})

test('technique filter and custom include', () => {
  const query = translate([
    { include: ['datasets', 'affiliation', 'person'] },
    {
      id: 'technique',
      value: 'test',
    },
  ])

  expect(query).toEqual({
    include: [
      {
        relation: 'members',
        scope: {
          include: [{ relation: 'affiliation' }, { relation: 'person' }],
        },
      },
      {
        relation: 'datasets',
        scope: {
          include: [
            {
              relation: 'techniques',
              scope: {
                where: {
                  name: 'test',
                },
              },
            },
          ],
        },
      },
    ],
    limit: 50,
  })
})

test('multiple filters and custom include', () => {
  const query = translate([
    { include: ['datasets', 'affiliation', 'person'] },
    {
      id: 'technique',
      value: 'test',
    },
    {
      id: 'sample_temperature',
      value: ['0', '7300'],
      operator: 'between',
      unit: 'K',
    },
  ])

  expect(query).toEqual({
    include: [
      {
        relation: 'members',
        scope: {
          include: [{ relation: 'affiliation' }, { relation: 'person' }],
        },
      },
      {
        relation: 'datasets',
        scope: {
          include: [
            {
              relation: 'techniques',
              scope: {
                where: {
                  name: 'test',
                },
              },
            },
            {
              relation: 'parameters',
              scope: {
                where: {
                  and: [
                    { name: 'sample_temperature' },
                    { value: { between: ['0', '7300'] } },
                    { unit: 'K' },
                  ],
                },
              },
            },
          ],
        },
      },
    ],
    limit: 50,
  })
})

test('all loopback query keys recognized by id', () => {
  const query = translate([
    { id: 'skip', value: 20 },
    { id: 'limit', value: 20 },
    { id: 'include', value: ['parameters'] },
    { id: 'order', value: ['foo ASC', 'bar DESC'] },
  ])
  expect(query).toEqual({
    include: [
      {
        relation: 'datasets',
        scope: { include: [{ relation: 'parameters' }] },
      },
    ],
    order: ['foo ASC', 'bar DESC'],
    skip: 20,
    limit: 20,
  })
})
