/* eslint-disable react/only-export-components */
import React, { createContext, useContext, useState } from 'react'

export interface Column {
  id: string
  name: string
  type: string
  isPrimaryKey: boolean
  isNullable: boolean
  defaultValue: string
}

export interface Table {
  id: string
  name: string
  columns: Column[]
}

export interface Relationship {
  id: string
  name: string
  sourceTableId: string
  sourceColumnId: string
  targetTableId: string
  targetColumnId: string
  type: 'one-to-one' | 'one-to-many' | 'many-to-one' | 'many-to-many'
  isRequired: boolean
  cascadeDelete: boolean
  cascadeUpdate: boolean
}

interface SchemaContextType {
  tables: Table[]
  setTables: React.Dispatch<React.SetStateAction<Table[]>>
  relationships: Relationship[]
  setRelationships: React.Dispatch<React.SetStateAction<Relationship[]>>
}

const SchemaContext = createContext<SchemaContextType | undefined>(undefined)

export const SchemaProvider = ({ children }: { children: React.ReactNode }) => {
  const [tables, setTables] = useState<Table[]>([
    {
      id: '1',
      name: 'users',
      columns: [
        {
          id: 'c1',
          name: 'id',
          type: 'INTEGER',
          isPrimaryKey: true,
          isNullable: false,
          defaultValue: '',
        },
        {
          id: 'c2',
          name: 'email',
          type: 'VARCHAR',
          isPrimaryKey: false,
          isNullable: false,
          defaultValue: '',
        },
        {
          id: 'c3',
          name: 'created_at',
          type: 'TIMESTAMP',
          isPrimaryKey: false,
          isNullable: false,
          defaultValue: 'CURRENT_TIMESTAMP',
        },
      ],
    },
    {
      id: '2',
      name: 'orders',
      columns: [
        {
          id: 'o1',
          name: 'id',
          type: 'INTEGER',
          isPrimaryKey: true,
          isNullable: false,
          defaultValue: '',
        },
        {
          id: 'o2',
          name: 'user_id',
          type: 'INTEGER',
          isPrimaryKey: false,
          isNullable: false,
          defaultValue: '',
        },
        {
          id: 'o3',
          name: 'total',
          type: 'FLOAT',
          isPrimaryKey: false,
          isNullable: false,
          defaultValue: '0.00',
        },
        {
          id: 'o4',
          name: 'status',
          type: 'VARCHAR',
          isPrimaryKey: false,
          isNullable: false,
          defaultValue: "'pending'",
        },
      ],
    },
  ])

  const [relationships, setRelationships] = useState<Relationship[]>([
    {
      id: 'r1',
      name: 'fk_orders_user_id',
      sourceTableId: '2',
      sourceColumnId: 'o2',
      targetTableId: '1',
      targetColumnId: 'c1',
      type: 'many-to-one',
      isRequired: true,
      cascadeDelete: true,
      cascadeUpdate: true,
    },
  ])

  return (
    <SchemaContext.Provider
      value={{ tables, setTables, relationships, setRelationships }}
    >
      {children}
    </SchemaContext.Provider>
  )
}

export const useSchema = () => {
  const context = useContext(SchemaContext)
  if (!context) throw new Error('useSchema must be used within SchemaProvider')
  return context
}
