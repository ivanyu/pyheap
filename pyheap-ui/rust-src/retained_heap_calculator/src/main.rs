//
// Copyright 2022 Ivan Yurchenko
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.
//

extern crate core;

use std::borrow::Borrow;
use std::collections::{HashMap, HashSet};
use std::io;
#[allow(unused_imports)]
use std::io::BufRead;
use std::time::Instant;
#[allow(unused_imports)]
use fnv::{FnvHashMap, FnvHashSet};

type MyHashMap<K, V> = FnvHashMap<K, V>;
type MyHashSet<T> = FnvHashSet<T>;

#[derive(Debug)]
struct HeapObject {
    size: u32,
    referents: MyHashSet<u64>,
    inbound_references: MyHashSet<u64>,
}

fn parse<T>(mut input: T) -> (MyHashMap<u64, HeapObject>, MyHashMap<String, MyHashSet<u64>>)
    where T: Iterator<Item = String>
{
    let mut objects: MyHashMap<u64, HeapObject> = MyHashMap::default();

    input.next().filter(|s| *s == "objects").expect("Broken input");

    loop {
        let addr = match input.next() {
            Some(s) if s == "threads" =>
                break,
            Some(s) if !s.is_empty() =>
                s.parse::<u64>().expect("Broken input"),
            _ => break
        };

        let size = match input.next() {
            Some(s) if !s.is_empty() => {
                s.parse::<u32>().expect("Broken input")
            },
            _ => break
        };

        let referents = input.next().map(parse_address_list)
            .expect("Broken input");
        let inbound_references = input.next().map(parse_address_list)
            .expect("Broken input");

        let obj = HeapObject { size, referents, inbound_references };
        objects.insert(addr, obj);
    }

    let mut threads: MyHashMap<String, MyHashSet<u64>> = MyHashMap::default();
    loop {
        let thread_name = match input.next() {
            Some(s) if !s.is_empty() => s,
            Some(s) if s.is_empty() => panic!("Broken input"),
            _ => break
        };
        let referents = input.next().map(parse_address_list)
            .expect("Broken input");
        threads.insert(thread_name, referents);
    }

    (objects, threads)
}

fn parse_address_list(s: String) -> MyHashSet<u64> {
    s.split_whitespace()
        .map(|el| match el.parse::<u64>() {
            Ok(i) => i,
            _ => panic!("Broken input")
        })
        .collect::<MyHashSet<u64>>()
}

struct RetainedHeapCalculator<> {
    objects: MyHashMap<u64, HeapObject>,
    threads: MyHashMap<String, MyHashSet<u64>>,
    object_retained_heap: MyHashMap<u64, u32>,
    thread_retained_heap: MyHashMap<String, u32>,
    subtree_roots: MyHashSet<u64>
}

impl RetainedHeapCalculator {
    pub fn new(objects: MyHashMap<u64, HeapObject>, threads: MyHashMap<String, MyHashSet<u64>>) -> RetainedHeapCalculator {
        RetainedHeapCalculator {
            objects,
            threads,
            object_retained_heap: MyHashMap::default(),
            thread_retained_heap: MyHashMap::default(),
            subtree_roots: MyHashSet::default()
        }
    }

    pub fn calculate(&mut self) {
        self.find_strict_subtrees();
        self.calculate_for_all_objects();
        self.calculate_for_all_threads()
    }

    fn find_strict_subtrees(&mut self) {
        let mut front: MyHashSet<u64> = MyHashSet::default();
        for (addr, obj) in self.objects.borrow() {
            if obj.referents.is_empty() && obj.inbound_references.len() < 2 {
                self.subtree_roots.insert(*addr);
                self.object_retained_heap.insert(*addr, obj.size);
                front.extend(obj.inbound_references.iter())
            }
        }

        let mut next_front: MyHashSet<u64> = MyHashSet::default();
        while &next_front != &front {
            for current_addr in front.iter() {
                let obj = self.objects.get(&current_addr).unwrap();
                // Skip if it has more than one inbound references.
                if obj.inbound_references.len() > 1 {
                    continue;
                }
                // Consider later if it has children not yet roots.
                if (&obj.referents - &(self.subtree_roots)).len() > 0 {
                    next_front.insert(*current_addr);
                    continue;
                }

                self.subtree_roots.insert(*current_addr);
                let ret_heap = obj.size + obj.referents.iter()
                    .map(|r| self.object_retained_heap.get(r).unwrap())
                    .sum::<u32>();
                self.object_retained_heap.insert(*current_addr, ret_heap);
                next_front.extend(obj.inbound_references.iter())
            }

            if front == next_front {
                break;
            }

            front.clear();
            front.extend(&next_front);
            next_front.clear();
        }
    }

    fn calculate_for_all_objects(&mut self) {
        let addrs = self.objects.keys()
            .cloned().collect::<Vec<u64>>();  // make borrow checker happy
        for addr in addrs {
            let mut inbound_reference_view: MyHashMap<u64, i32> = MyHashMap::default();
            // Imitate deletion of the initial address.
            inbound_reference_view.insert(addr, 0);
            let mut front = vec![addr];
            let ret_heap = self.retained_heap0(
                &mut inbound_reference_view,
                &mut front,
                true
            );
            self.object_retained_heap.insert(addr, ret_heap);
        }
    }

    fn calculate_for_all_threads(&mut self) {
        for (thread, locals) in self.threads.clone() {
            let mut inbound_reference_view: MyHashMap<u64, i32> = MyHashMap::default();
            for obj in locals.iter() {
                let view = self.objects.get(obj).unwrap().inbound_references.len() as i32;
                inbound_reference_view.insert(*obj, view);

                for (other_thread, other_locals) in self.threads.iter() {
                    if *other_thread == *thread {
                        continue
                    }
                    if other_locals.contains(obj) {
                        *inbound_reference_view.get_mut(obj).unwrap() += 1;
                    }
                }
            }

            let mut front = locals.iter().cloned().collect::<Vec<u64>>();
            let ret_heap = self.retained_heap0(
                &mut inbound_reference_view,
                &mut front,
                false,
            );
            self.thread_retained_heap.insert(thread, ret_heap);
        }
    }

    fn retained_heap0(&mut self,
                      inbound_reference_view: &mut MyHashMap<u64, i32>,
                      front: &mut Vec<u64>,
                      use_subtrees: bool
    ) -> u32 {
        let mut result: u32 = 0;
        let mut deleted: MyHashSet<u64> = MyHashSet::default();

        loop {
            front.sort_by_key(|x| inbound_reference_view.get(x).unwrap());
            front.reverse();

            let (retained, deletion_happened) = self.retained_heap_calculation_iteration(
                front, inbound_reference_view, &mut deleted, use_subtrees
            );
            if !deletion_happened {
                assert_eq!(retained, 0);
                break;
            }
            result += retained;
        }
        result
    }

    fn retained_heap_calculation_iteration(&mut self,
                                           front: &mut Vec<u64>,
                                           inbound_reference_view: &mut MyHashMap<u64, i32>,
                                           deleted: &mut MyHashSet<u64>,
                                           use_subtrees: bool) -> (u32, bool) {
        let mut retained: u32 = 0;
        let mut deletion_happened = false;

        for i in (0..front.len()).rev() {
            let current = front[i];

            if *inbound_reference_view.get(&current).unwrap() > 0 {
                break;
            }
            if deleted.contains(&current) {
                continue;
            }

            front.remove(i);
            deleted.insert(current);
            deletion_happened = true;

            if use_subtrees && self.subtree_roots.contains(&current) {
                retained += self.object_retained_heap.get(&current).unwrap();
            } else if self.objects.contains_key(&current) {
                let obj = self.objects.get(&current).unwrap();
                retained += obj.size;
                let to_be_added_to_front = &(obj.referents) - deleted;
                self.update_inbound_references_view(&to_be_added_to_front, inbound_reference_view);
                front.extend(to_be_added_to_front);
            }
        }

        (retained, deletion_happened)
    }

    fn update_inbound_references_view(&mut self,
                                      to_be_added_to_front: &MyHashSet<u64>,
                                      inbound_reference_view: &mut MyHashMap<u64, i32>) {
        for r in to_be_added_to_front {
            match inbound_reference_view.get_mut(r) {
                Some(v) => *v -= 1,
                None => {
                    match self.objects.get(r) {
                        Some(obj) => {
                            let view = (obj.inbound_references.len() - 1) as i32;
                            inbound_reference_view.insert(*r, view);
                        }
                        None => {
                            inbound_reference_view.insert(*r, 0);
                        }
                    }
                }
            }
        }
    }
}

fn main() {
//     let input_str =
// "objects
// 1
// 10
// 3
// 2
// 2
// 20
// 1 6
// 3
// 3
// 30
// 2 4
// 1 5
// 4
// 40
// 5
// 3
// 5
// 50
// 3
// 4
// 6
// 60
// 7
// 2
// 7
// 70
//
// 6
// threads
// thread1
// 1 2
// thread2
// 5 7";

    let start = Instant::now();
    let input = io::stdin().lines()
        .map(|r| r.expect("Broken input"));
    // let input = io::Cursor::new(input_str).lines()
    //     .map(|r| r.expect("Broken input"));
    let duration = start.elapsed();

    let (objects, threads) = parse(input);
    // println!("Objects: {:?}", objects);
    eprintln!("Input read and parsed in {} s", duration.as_secs());

    let mut retained_heap_calculator = RetainedHeapCalculator::new(objects, threads);
    retained_heap_calculator.calculate();

    println!("objects");
    for (addr, ret_heap) in retained_heap_calculator.object_retained_heap {
        println!("{} {}", addr, ret_heap)
    }
    println!("threads");
    for (thread, ret_heap) in retained_heap_calculator.thread_retained_heap {
        println!("{} {}", thread, ret_heap)
    }
}
