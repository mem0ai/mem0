"use client";

import { useState, useEffect } from "react";
import { Separator } from "@/components/ui/separator";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import Link from "next/link";

export default function Page() {
  const [collections, setCollections] = useState([]);

  useEffect(() => {
    fetch("/api/v1/admin/collections")
      .then((response) => response.json())
      .then((data) => {
        setCollections(data);
      });
  }, []);

  return (
    <div className="mt-20 flex justify-center items-stretch">
      <div className="max-w-screen-lg w-full bg-background">
        <div className="p-4 md:p-8 flex flex-col h-full">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              {" "}
              {/* Right-align heading and tooltip */}
              <h2 className="text-2xl font-semibold tracking-tight">
                Vector store collections
              </h2>
            </div>
          </div>
          <h3 className="text-sm text-muted-foreground">
            See list of collections/indices present in your vector store.
          </h3>
          <Separator className="my-4" />
          <Table>
            <TableHeader>
              <TableRow>
                {/* <TableHead className="w-[100px]">Id</TableHead> */}
                <TableHead>Name</TableHead>
                <TableHead>Tenant</TableHead>
                <TableHead>Database</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {collections.map((collection) => (
                <TableRow key={collection.id}>
                  <TableCell className="font-sm underline underline-offset-2">
                    <Link
                      href={`/admin/chromadb/collections/${collection.name}`}
                    >
                      {collection.name}
                    </Link>
                  </TableCell>
                  {/* <TableCell>{collection.name}</TableCell> */}
                  <TableCell>{collection?.tenant}</TableCell>
                  <TableCell>{collection?.database}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </div>
    </div>
  );
}
