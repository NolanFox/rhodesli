// https://donatso.github.io/family-chart/ v0.2.1 Copyright 2024 donatso
(function (global, factory) {
typeof exports === 'object' && typeof module !== 'undefined' ? module.exports = factory(require('d3')) :
typeof define === 'function' && define.amd ? define(['d3'], factory) :
(global = typeof globalThis !== 'undefined' ? globalThis : global || self, global.f3 = factory(global.f3));
}(this, (function (_d3) { 'use strict';

function _interopNamespace(e) {
if (e && e.__esModule) return e;
var n = Object.create(null);
if (e) {
Object.keys(e).forEach(function (k) {
if (k !== 'default') {
var d = Object.getOwnPropertyDescriptor(e, k);
Object.defineProperty(n, k, d.get ? d : {
enumerable: true,
get: function () {
return e[k];
}
});
}
});
}
n['default'] = e;
return Object.freeze(n);
}

var _d3__namespace = /*#__PURE__*/_interopNamespace(_d3);

var d3 = typeof window === "object" && !!window.d3 ? window.d3 : _d3__namespace;

function sortChildrenWithSpouses(data) {
  data.forEach(datum => {
    if (!datum.rels.children) return
    const spouses = datum.rels.spouses || [];
    datum.rels.children.sort((a, b) => {
      const a_d = data.find(d => d.id === a),
        b_d = data.find(d => d.id === b),
        a_p2 = otherParent(a_d, datum, data) || {},
        b_p2 = otherParent(b_d, datum, data) || {},
        a_i = spouses.indexOf(a_p2.id),
        b_i = spouses.indexOf(b_p2.id);

      if (datum.data.gender === "M") return a_i - b_i
      else return b_i - a_i
    });
  });
}

function otherParent(d, p1, data) {
  return data.find(d0 => (d0.id !== p1.id) && ((d0.id === d.rels.mother) || (d0.id === d.rels.father)))
}

function calculateEnterAndExitPositions(d, entering, exiting) {
  d.exiting = exiting;
  if (entering) {
    if (d.depth === 0 && !d.spouse) {d._x = d.x; d._y = d.y;}
    else if (d.spouse) {d._x = d.spouse.x; d._y = d.spouse.y;}
    else if (d.is_ancestry) {d._x = d.parent.x; d._y = d.parent.y;}
    else {d._x = d.psx; d._y = d.psy;}
  } else if (exiting) {
    const x = d.x > 0 ? 1 : -1,
      y = d.y > 0 ? 1 : -1;
    {d._x = d.x+400*x; d._y = d.y+400*y;}
  }
}

function toggleRels(tree_datum, hide_rels) {
  const
    rels = hide_rels ? 'rels' : '_rels',
    rels_ = hide_rels ? '_rels' : 'rels';
  
  if (tree_datum.is_ancestry || tree_datum.data.main) {showHideAncestry('father'); showHideAncestry('mother');}
  else {showHideChildren();}

  function showHideAncestry(rel_type) {
    if (!tree_datum.data[rels] || !tree_datum.data[rels][rel_type]) return
    if (!tree_datum.data[rels_]) tree_datum.data[rels_] = {};
    tree_datum.data[rels_][rel_type] = tree_datum.data[rels][rel_type];
    delete tree_datum.data[rels][rel_type];
  }

  function showHideChildren() {
    if (!tree_datum.data[rels] || !tree_datum.data[rels].children) return
    const
      children = tree_datum.data[rels].children.slice(0),
      spouses = tree_datum.spouse ? [tree_datum.spouse] : tree_datum.spouses || [];

    [tree_datum, ...spouses].forEach(sp => children.forEach(ch_id => {
      if (sp.data[rels].children.includes(ch_id)) {
        if (!sp.data[rels_]) sp.data[rels_] = {};
        if (!sp.data[rels_].children) sp.data[rels_].children = [];
        sp.data[rels_].children.push(ch_id);
        sp.data[rels].children.splice(sp.data[rels].children.indexOf(ch_id), 1);
      }
    }));
  }
}

function toggleAllRels(tree_data, hide_rels) {
  tree_data.forEach(d => {d.data.hide_rels = hide_rels; toggleRels(d, hide_rels);});
}

function checkIfRelativesConnectedWithoutPerson(datum, data_stash) {
  const r = datum.rels,
    r_ids = [r.father, r.mother, ...(r.spouses || []), ...(r.children || [])].filter(r_id => !!r_id),
    rels_not_to_main = [];

  for (let i = 0; i < r_ids.length; i++) {
    const line = findPersonLineToMain(data_stash.find(d => d.id === r_ids[i]), [datum]);
    if (!line) {rels_not_to_main.push(r_ids[i]); break;}
  }
  return rels_not_to_main.length === 0;

  function findPersonLineToMain(datum, without_persons) {
    let line;
    if (isM(datum)) line = [datum];
    checkIfAnyRelIsMain(datum, [datum]);
    return line

    function checkIfAnyRelIsMain(d0, history) {
      if (line) return
      history = [...history, d0];
      runAllRels(check);
      if (!line) runAllRels(checkRels);

      function runAllRels(f) {
        const r = d0.rels;
        [r.father, r.mother, ...(r.spouses || []), ...(r.children || [])]
          .filter(d_id => (d_id && ![...without_persons, ...history].find(d => d.id === d_id)))
          .forEach(d_id => f(d_id));
      }

      function check(d_id) {
        if (isM(d_id)) line = history;
      }

      function checkRels(d_id) {
        const person = data_stash.find(d => d.id === d_id);
        checkIfAnyRelIsMain(person, history);
      }
    }
  }
  function isM(d0) {return typeof d0 === 'object' ? d0.id === data_stash[0].id : d0 === data_stash[0].id}  // todo: make main more exact
}

function createForm({datum, store, fields, postSubmit, addRelative, deletePerson, onCancel, editFirst}) {
  const form_creator = {
    fields: [],
    onSubmit: submitFormChanges,
  };
  if (!datum._new_rel_data) {
    form_creator.onDelete = deletePersonWithPostSubmit;
    form_creator.addRelative = () => addRelative.activate(datum),
    form_creator.addRelativeCancel = () => addRelative.onCancel();
    form_creator.addRelativeActive = addRelative.is_active;

    form_creator.editable = false;
  }
  if (datum._new_rel_data) {
    form_creator.title = datum._new_rel_data.label;
    form_creator.new_rel = true;
    form_creator.editable = true;
    form_creator.onCancel = onCancel;
  }
  if (form_creator.onDelete) form_creator.can_delete = checkIfRelativesConnectedWithoutPerson(datum, store.getData());

  if (editFirst) form_creator.editable = true;

  form_creator.gender_field = {
    id: 'gender', 
    type: 'switch',
    label: 'Gender',
    initial_value: datum.data.gender,
    options: [{value: 'M', label: 'Male'}, {value: 'F', label: 'Female'}]
  };

  fields.forEach(d => {
    const field = {
      id: d.id,
      type: d.type,
      label: d.label,
      initial_value: datum.data[d.id],
    };
    form_creator.fields.push(field);
  });

  return form_creator

  function submitFormChanges(e) {
    e.preventDefault();
    const form_data = new FormData(e.target);
    form_data.forEach((v, k) => datum.data[k] = v);
    if (datum.to_add) delete datum.to_add;
    postSubmit();
  }

  function deletePersonWithPostSubmit() {
    deletePerson();
    postSubmit({delete: true});
  }
}

function moveToAddToAdded(datum, data_stash) {
  delete datum.to_add;
  return datum
}

function removeToAdd(datum, data_stash) {
  deletePerson(datum, data_stash);
  return false
}

function deletePerson(datum, data_stash) {
  if (!checkIfRelativesConnectedWithoutPerson(datum, data_stash)) return {success: false, error: 'checkIfRelativesConnectedWithoutPerson'}
  executeDelete();
  return {success: true};

  function executeDelete() {
    data_stash.forEach(d => {
      for (let k in d.rels) {
        if (!d.rels.hasOwnProperty(k)) continue
        if (d.rels[k] === datum.id) {
          delete d.rels[k];
        } else if (Array.isArray(d.rels[k]) && d.rels[k].includes(datum.id)) {
          d.rels[k].splice(d.rels[k].findIndex(did => did === datum.id), 1);
        }
      }
    });
    data_stash.splice(data_stash.findIndex(d => d.id === datum.id), 1);
    data_stash.forEach(d => {if (d.to_add) deletePerson(d, data_stash);});  // full update of tree
    if (data_stash.length === 0) data_stash.push(createTreeDataWithMainNode({}).data[0]);
  }
}

function cleanupDataJson(data_json) {
  let data_no_to_add = JSON.parse(data_json);
  data_no_to_add.forEach(d => d.to_add ? removeToAdd(d, data_no_to_add) : d);
  data_no_to_add.forEach(d => delete d.main);
  data_no_to_add.forEach(d => delete d.hide_rels);
  return JSON.stringify(data_no_to_add, null, 2)
}

function removeToAddFromData(data) {
  data.forEach(d => d.to_add ? removeToAdd(d, data) : d);
  return data
}

function handleRelsOfNewDatum({datum, data_stash, rel_type, rel_datum}) {
  if (rel_type === "daughter" || rel_type === "son") addChild(datum);
  else if (rel_type === "father" || rel_type === "mother") addParent(datum);
  else if (rel_type === "spouse") addSpouse(datum);

  function addChild(datum) {
    if (datum.data.other_parent) {
      addChildToSpouseAndParentToChild(datum.data.other_parent);
      delete datum.data.other_parent;
    }
    datum.rels[rel_datum.data.gender === 'M' ? 'father' : 'mother'] = rel_datum.id;
    if (!rel_datum.rels.children) rel_datum.rels.children = [];
    rel_datum.rels.children.push(datum.id);
    return datum

    function addChildToSpouseAndParentToChild(spouse_id) {
      if (spouse_id === "_new") spouse_id = addOtherParent().id;

      const spouse = data_stash.find(d => d.id === spouse_id);
      datum.rels[spouse.data.gender === 'M' ? 'father' : 'mother'] = spouse.id;
      if (!spouse.rels.hasOwnProperty('children')) spouse.rels.children = [];
      spouse.rels.children.push(datum.id);

      function addOtherParent() {
        const new_spouse = createNewPersonWithGenderFromRel({rel_type: "spouse", rel_datum});
        addSpouse(new_spouse);
        addNewPerson({data_stash, datum: new_spouse});
        return new_spouse
      }
    }
  }

  function addParent(datum) {
    const is_father = datum.data.gender === "M",
      parent_to_add_id = rel_datum.rels[is_father ? 'father' : 'mother'];
    if (parent_to_add_id) removeToAdd(data_stash.find(d => d.id === parent_to_add_id), data_stash);
    addNewParent();

    function addNewParent() {
      rel_datum.rels[is_father ? 'father' : 'mother'] = datum.id;
      handleSpouse();
      datum.rels.children = [rel_datum.id];
      return datum

      function handleSpouse() {
        const spouse_id = rel_datum.rels[!is_father ? 'father' : 'mother'];
        if (!spouse_id) return
        const spouse = data_stash.find(d => d.id === spouse_id);
        datum.rels.spouses = [spouse_id];
        if (!spouse.rels.spouses) spouse.rels.spouses = [];
        spouse.rels.spouses.push(datum.id);
        return spouse
      }
    }
  }

  function addSpouse(datum) {
    removeIfToAdd();
    if (!rel_datum.rels.spouses) rel_datum.rels.spouses = [];
    rel_datum.rels.spouses.push(datum.id);
    datum.rels.spouses = [rel_datum.id];

    function removeIfToAdd() {
      if (!rel_datum.rels.spouses) return
      rel_datum.rels.spouses.forEach(spouse_id => {
        const spouse = data_stash.find(d => d.id === spouse_id);
        if (spouse.to_add) removeToAdd(spouse, data_stash);
      });
    }
  }
}

function handleNewRel({datum, new_rel_datum, data_stash}) {
  const rel_type = new_rel_datum._new_rel_data.rel_type;
  delete new_rel_datum._new_rel_data;
  new_rel_datum = JSON.parse(JSON.stringify(new_rel_datum));  // to keep same datum state in current add relative tree

  if (rel_type === "son" || rel_type === "daughter") {
    let mother = data_stash.find(d => d.id === new_rel_datum.rels.mother);
    let father = data_stash.find(d => d.id === new_rel_datum.rels.father);

    new_rel_datum.rels = {};
    if (father) {
      if (!father.rels.children) father.rels.children = [];
      father.rels.children.push(new_rel_datum.id);
      new_rel_datum.rels.father = father.id;
    }
    if (mother) {
      if (!mother.rels.children) mother.rels.children = [];
      mother.rels.children.push(new_rel_datum.id);
      new_rel_datum.rels.mother = mother.id;
    }
  }

  else if (rel_type === "spouse") {
    if (!datum.rels.spouses) datum.rels.spouses = [];
    if (!datum.rels.spouses.includes(new_rel_datum.id)) datum.rels.spouses.push(new_rel_datum.id);

    // if rel is added in same same add relative tree then we need to clean up duplicate parent
    new_rel_datum.rels.children = new_rel_datum.rels.children.filter(child_id => {
      const child = data_stash.find(d => d.id === child_id);
      if (!child) return false
      if (child.rels.mother !== datum.id) {
        if (data_stash.find(d => d.id === child.rels.mother)) data_stash.splice(data_stash.findIndex(d => d.id === child.rels.mother), 1);
        child.rels.mother = new_rel_datum.id;
      }
      if (child.rels.father !== datum.id) {
        if (data_stash.find(d => d.id === child.rels.father)) data_stash.splice(data_stash.findIndex(d => d.id === child.rels.father), 1);
        child.rels.father = new_rel_datum.id;
      }
      return true
    });

    new_rel_datum.rels = {
      spouses: [datum.id],
      children: new_rel_datum.rels.children
    };
  }

  else if (rel_type === "father") {
    datum.rels.father = new_rel_datum.id;
    new_rel_datum.rels = {
      children: [datum.id],
    };
    if (datum.rels.mother) {
      new_rel_datum.rels.spouses = [datum.rels.mother];
      const mother = data_stash.find(d => d.id === datum.rels.mother);
      if (!mother.rels.spouses) mother.rels.spouses = [];
      mother.rels.spouses.push(new_rel_datum.id);
    }
  }

  else if (rel_type === "mother") {
    datum.rels.mother = new_rel_datum.id;
    new_rel_datum.rels = {
      children: [datum.id],
    };
    if (datum.rels.father) {
      new_rel_datum.rels.spouses = [datum.rels.father];
      const father = data_stash.find(d => d.id === datum.rels.father);
      if (!father.rels.spouses) father.rels.spouses = [];
      father.rels.spouses.push(new_rel_datum.id);
    }
  }

  data_stash.push(new_rel_datum);
}

function createNewPerson({data, rels}) {
  return {id: generateUUID(), data: data || {}, rels: rels || {}}
}

function createNewPersonWithGenderFromRel({data, rel_type, rel_datum}) {
  const gender = getGenderFromRelative(rel_datum, rel_type);
  data = Object.assign(data || {}, {gender});
  return createNewPerson({data})

  function getGenderFromRelative(rel_datum, rel_type) {
    return (["daughter", "mother"].includes(rel_type) || rel_type === "spouse" && rel_datum.data.gender === "M") ? "F" : "M"
  }
}

function addNewPerson({data_stash, datum}) {
  data_stash.push(datum);
}

function createTreeDataWithMainNode({data, version}) {
  return {data: [createNewPerson({data})], version}
}

function addNewPersonAndHandleRels({datum, data_stash, rel_type, rel_datum}) {
  addNewPerson({data_stash, datum});
  handleRelsOfNewDatum({datum, data_stash, rel_type, rel_datum});
}

function generateUUID() {
  var d = new Date().getTime();
  var d2 = (performance && performance.now && (performance.now()*1000)) || 0;//Time in microseconds since page-load or 0 if unsupported
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    var r = Math.random() * 16;
    if(d > 0){//Use timestamp until depleted
      r = (d + r)%16 | 0;
      d = Math.floor(d/16);
    } else {//Use microseconds since page-load if supported
      r = (d2 + r)%16 | 0;
      d2 = Math.floor(d2/16);
    }
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

function manualZoom({amount, svg, transition_time=500}) {
  const zoom = svg.__zoomObj;
  d3.select(svg).transition().duration(transition_time || 0).delay(transition_time ? 100 : 0)  // delay 100 because of weird error of undefined something in d3 zoom
    .call(zoom.scaleBy, amount);
}

function isAllRelativeDisplayed(d, data) {
  const r = d.data.rels,
    all_rels = [r.father, r.mother, ...(r.spouses || []), ...(r.children || [])].filter(v => v);
  return all_rels.every(rel_id => data.some(d => d.data.id === rel_id))
}

function CalculateTree({data, main_id=null, node_separation=250, level_separation=150, single_parent_empty_card=true, is_horizontal=false}) {
  if (!data || !data.length) return {data: [], data_stash: [], dim: {width: 0, height: 0}, main_id: null}
  if (is_horizontal) [node_separation, level_separation] = [level_separation, node_separation];
  const data_stash = single_parent_empty_card ? createRelsToAdd(data) : data;
  sortChildrenWithSpouses(data_stash);
  const main = (main_id !== null && data_stash.find(d => d.id === main_id)) || data_stash[0];
  const tree_children = calculateTreePositions(main, 'children', false);
  const tree_parents = calculateTreePositions(main, 'parents', true);

  data_stash.forEach(d => d.main = d === main);
  levelOutEachSide(tree_parents, tree_children);
  const tree = mergeSides(tree_parents, tree_children);
  setupChildrenAndParents({tree});
  setupSpouses({tree, node_separation});
  setupProgenyParentsPos({tree});
  nodePositioning({tree});
  tree.forEach(d => d.all_rels_displayed = isAllRelativeDisplayed(d, tree));

  const dim = calculateTreeDim(tree, node_separation, level_separation);

  return {data: tree, data_stash, dim, main_id: main.id, is_horizontal}

  function calculateTreePositions(datum, rt, is_ancestry) {
    const hierarchyGetter = rt === "children" ? hierarchyGetterChildren : hierarchyGetterParents,
      d3_tree = d3.tree().nodeSize([node_separation, level_separation]).separation(separation),
      root = d3.hierarchy(datum, hierarchyGetter);
    d3_tree(root);
    return root.descendants()

    function separation(a, b) {
      let offset = 1;
      if (!is_ancestry) {
        if (!sameParent(a, b)) offset+=.25;
        if (someSpouses(a,b)) offset+=offsetOnPartners(a,b);
        if (sameParent(a, b) && !sameBothParents(a,b)) offset+=.125;
      }
      return offset
    }
    function sameParent(a, b) {return a.parent == b.parent}
    function sameBothParents(a, b) {return (a.data.rels.father === b.data.rels.father) && (a.data.rels.mother === b.data.rels.mother)}
    function hasSpouses(d) {return d.data.rels.spouses && d.data.rels.spouses.length > 0}
    function someSpouses(a, b) {return hasSpouses(a) || hasSpouses(b)}

    function hierarchyGetterChildren(d) {
      return [...(d.rels.children || [])].map(id => data_stash.find(d => d.id === id))
    }

    function hierarchyGetterParents(d) {
      return [d.rels.father, d.rels.mother]
        .filter(d => d).map(id => data_stash.find(d => d.id === id))
    }

    function offsetOnPartners(a,b) {
      return ((a.data.rels.spouses || []).length + (b.data.rels.spouses || []).length)*.5
    }
  }

  function levelOutEachSide(parents, children) {
    const mid_diff = (parents[0].x - children[0].x) / 2;
    parents.forEach(d => d.x-=mid_diff);
    children.forEach(d => d.x+=mid_diff);
  }

  function mergeSides(parents, children) {
    parents.forEach(d => {d.is_ancestry = true;});
    parents.forEach(d => d.depth === 1 ? d.parent = children[0] : null);

    return [...children, ...parents.slice(1)];
  }
  function nodePositioning({tree}) {
    tree.forEach(d => {
      d.y *= (d.is_ancestry ? -1 : 1);
      if (is_horizontal) {
        const d_x = d.x; d.x = d.y; d.y = d_x;
      }
    });
  }

  function setupSpouses({tree, node_separation}) {
    for (let i = tree.length; i--;) {
      const d = tree[i];
      if (!d.is_ancestry && d.data.rels.spouses && d.data.rels.spouses.length > 0){
        const side = d.data.data.gender === "M" ? -1 : 1;  // female on right
        d.x += d.data.rels.spouses.length/2*node_separation*side;
        d.data.rels.spouses.forEach((sp_id, i) => {
          const spouse = {data: data_stash.find(d0 => d0.id === sp_id), added: true};

          spouse.x = d.x-(node_separation*(i+1))*side;
          spouse.y = d.y;
          spouse.sx = i > 0 ? spouse.x : spouse.x + (node_separation/2)*side;
          spouse.sy = i > 0 ? spouse.y : spouse.y + (node_separation/2)*side;
          spouse.depth = d.depth;
          spouse.spouse = d;
          if (!d.spouses) d.spouses = [];
          d.spouses.push(spouse);
          tree.push(spouse);
        });
      }
      if (d.parents && d.parents.length === 2) {
        const p1 = d.parents[0],
          p2 = d.parents[1],
          midd = p1.x - (p1.x - p2.x)/2,
          x = (d,sp) => midd + (node_separation/2)*(d.x < sp.x ? 1 : -1);

        p2.x = x(p1, p2); p1.x = x(p2, p1);
      }
    }
  }

  function setupProgenyParentsPos({tree}) {
    tree.forEach(d => {
      if (d.is_ancestry) return
      if (d.depth === 0) return
      if (d.added) return
      const m = findDatum(d.data.rels.mother);
      const f = findDatum(d.data.rels.father);
      if (m && f) {
        if (!m.added && !f.added) console.error('no added spouse', m, f);
        const added_spouse = m.added ? m : f;
        setupParentPos(d, added_spouse);
      } else if (m || f) {
        const parent = m || f;
        parent.sx = parent.x;
        parent.sy = parent.y;
        setupParentPos(d, parent);
      }

      function setupParentPos(d, p) {
        d.psx = !is_horizontal ? p.sx : p.y;
        d.psy = !is_horizontal ? p.y : p.sx;
      }
    });

    function findDatum(id) {
      if (!id) return null
      return tree.find(d => d.data.id === id)
    }
  }

  function setupChildrenAndParents({tree}) {
    tree.forEach(d0 => {
      delete d0.children;
      tree.forEach(d1 => {
        if (d1.parent === d0) {
          if (d1.is_ancestry) {
            if (!d0.parents) d0.parents = [];
            d0.parents.push(d1);
          } else {
            if (!d0.children) d0.children = [];
            d0.children.push(d1);
          }
        }
      });
    });
  }

  function calculateTreeDim(tree, node_separation, level_separation) {
    if (is_horizontal) [node_separation, level_separation] = [level_separation, node_separation];
    const w_extent = d3.extent(tree, d => d.x);
    const h_extent = d3.extent(tree, d => d.y);
    return {
      width: w_extent[1] - w_extent[0]+node_separation, height: h_extent[1] - h_extent[0]+level_separation, x_off: -w_extent[0]+node_separation/2, y_off: -h_extent[0]+level_separation/2
    }
  }

  function createRelsToAdd(data) {
    const to_add_spouses = [];
    for (let i = 0; i < data.length; i++) {
      const d = data[i];
      if (d.rels.children && d.rels.children.length > 0) {
        if (!d.rels.spouses) d.rels.spouses = [];
        const is_father = d.data.gender === "M";
        let spouse;

        d.rels.children.forEach(d0 => {
          const child = data.find(d1 => d1.id === d0);
          if (child.rels[is_father ? 'father' : 'mother'] !== d.id) return
          if (child.rels[!is_father ? 'father' : 'mother']) return
          if (!spouse) {
            spouse = createToAddSpouse(d);
            d.rels.spouses.push(spouse.id);
          }
          spouse.rels.children.push(child.id);
          child.rels[!is_father ? 'father' : 'mother'] = spouse.id;
        });
      }
    }
    to_add_spouses.forEach(d => data.push(d));
    return data

    function createToAddSpouse(d) {
      const spouse = createNewPerson({
        data: {gender: d.data.gender === "M" ? "F" : "M"},
        rels: {spouses: [d.id], children: []}
      });
      spouse.to_add = true;
      to_add_spouses.push(spouse);
      return spouse
    }
  }

}

function createStore(initial_state) {
  let onUpdate;
  const state = initial_state;
  state.main_id_history = []; 

  const store = {
    state,
    updateTree: (props) => {
      state.tree = calcTree();
      if (!state.main_id) updateMainId(state.tree.main_id);
      if (onUpdate) onUpdate(props);
    },
    updateData: data => state.data = data,
    updateMainId,
    getMainId: () => state.main_id,
    getData: () => state.data,
    getTree: () => state.tree,
    setOnUpdate: (f) => onUpdate = f,

    getMainDatum,
    getDatum,
    getTreeMainDatum,
    getTreeDatum,
    getLastAvailableMainDatum,

    methods: {},
  };

  return store

  function calcTree() {
    return CalculateTree({
      data: state.data, main_id: state.main_id,
      node_separation: state.node_separation, level_separation: state.level_separation,
      single_parent_empty_card: state.single_parent_empty_card,
      is_horizontal: state.is_horizontal
    })
  }

  function getMainDatum() {
    return state.data.find(d => d.id === state.main_id)
  }

  function getDatum(id) {
    return state.data.find(d => d.id === id)
  }

  function getTreeMainDatum() {
    if (!state.tree) return null;
    return state.tree.data.find(d => d.data.id === state.main_id)
  }

  function getTreeDatum(id) {
    if (!state.tree) return null;
    return state.tree.data.find(d => d.id === id)
  }

  function updateMainId(id) {
    if (id === state.main_id) return
    state.main_id_history = state.main_id_history.filter(d => d !== id).slice(-10);
    state.main_id_history.push(id);
    state.main_id = id;
  }

  // if main_id is deleted, get the last available main_id
  function getLastAvailableMainDatum() {
    let main_id = state.main_id_history.slice(0).reverse().find(id => getDatum(id));
    if (!main_id) main_id = state.data[0].id;
    if (main_id !== state.main_id) updateMainId(main_id);
    return getDatum(main_id)
  }
}

function positionTree({t, svg, transition_time=2000}) {
  const el_listener = svg.__zoomObj ? svg : svg.parentNode;  // if we need listener for svg and html, we will use parent node
  const zoom = el_listener.__zoomObj;

  d3.select(el_listener).transition().duration(transition_time || 0).delay(transition_time ? 100 : 0)  // delay 100 because of weird error of undefined something in d3 zoom
    .call(zoom.transform, d3.zoomIdentity.scale(t.k).translate(t.x, t.y));
}

function treeFit({svg, svg_dim, tree_dim, with_transition, transition_time}) {
  const t = calculateTreeFit(svg_dim, tree_dim);
  positionTree({t, svg, with_transition, transition_time});
}

function calculateTreeFit(svg_dim, tree_dim) {
  let k = Math.min(svg_dim.width / tree_dim.width, svg_dim.height / tree_dim.height);
  if (k > 1) k = 1;
  const x = tree_dim.x_off + (svg_dim.width - tree_dim.width*k)/k/2;
  const y = tree_dim.y_off + (svg_dim.height - tree_dim.height*k)/k/2;

  return {k,x,y}
}

function cardToMiddle({datum, svg, svg_dim, scale, transition_time}) {
  const k = scale || 1, x = svg_dim.width/2-datum.x*k, y = svg_dim.height/2-datum.y,
    t = {k, x: x/k, y: y/k};
  positionTree({t, svg, with_transition: true, transition_time});
}

function createLinks({d, tree, is_horizontal=false}) {
  const links = [];

  if (d.data.rels.spouses && d.data.rels.spouses.length > 0) handleSpouse({d});
  handleAncestrySide({d});
  handleProgenySide({d});

  return links;

  function handleAncestrySide({d}) {
    if (!d.parents) return
    const p1 = d.parents[0];
    const p2 = d.parents[1] || p1;

    const p = {x: getMid(p1, p2, 'x'), y: getMid(p1, p2, 'y')};

    links.push({
      d: Link(d, p),
      _d: () => {
        const _d = {x: d.x, y: d.y},
          _p = {x: d.x, y: d.y};
        return Link(_d, _p)
      },
      curve: true, 
      id: linkId(d, p1, p2), 
      depth: d.depth+1, 
      is_ancestry: true,
      source: d,
      target: [p1, p2]
    });
  }


  function handleProgenySide({d}) {
    if (!d.children || d.children.length === 0) return

    d.children.forEach((child, i) => {
      const other_parent = otherParent(child, d, tree) || d;
      const sx = other_parent.sx;

      const parent_pos = !is_horizontal ? {x: sx, y: d.y} : {x: d.x, y: sx};
      links.push({
        d: Link(child, parent_pos),
        _d: () => Link(parent_pos, {x: _or(parent_pos, 'x'), y: _or(parent_pos, 'y')}),
        curve: true,
        id: linkId(child, d, other_parent),
        depth: d.depth+1,
        is_ancestry: false,
        source: [d, other_parent],
        target: child
      });
    });
  }


  function handleSpouse({d}) {
    d.data.rels.spouses.forEach(sp_id => {
      const spouse = getRel(d, tree, d0 => d0.data.id === sp_id);
      if (!spouse || d.spouse) return
      links.push({
        d: [[d.x, d.y], [spouse.x, spouse.y]],
        _d: () => [
          d.is_ancestry ? [_or(d, 'x')-.0001, _or(d, 'y')] : [d.x, d.y], // add -.0001 to line to have some length if d.x === spouse.x
          d.is_ancestry ? [_or(spouse, 'x'), _or(spouse, 'y')] : [d.x-.0001, d.y]
        ],
        curve: false, 
        id: linkId(d, spouse), 
        depth: d.depth, 
        spouse: true, 
        is_ancestry: spouse.is_ancestry, 
        source: d, 
        target: spouse
      });
    });
  }

  ///
  function getMid(d1, d2, side, is_) {
    if (is_) return _or(d1, side) - (_or(d1, side) - _or(d2, side))/2
    else return d1[side] - (d1[side] - d2[side])/2
  }

  function _or(d, k) {
   return d.hasOwnProperty('_'+k) ? d['_'+k] : d[k]
  }

  function Link(d, p) {
    return is_horizontal ? LinkHorizontal(d, p) : LinkVertical(d, p)
  }

  function LinkVertical(d, p) {
    const hy = (d.y + (p.y - d.y) / 2);
    return [
      [d.x, d.y],
      [d.x, hy],
      [d.x, hy],
      [p.x, hy],
      [p.x, hy],
      [p.x, p.y],
    ]
  }

  function LinkHorizontal(d, p) {
    const hx = (d.x + (p.x - d.x) / 2);
    return [
      [d.x, d.y],
      [hx, d.y],
      [hx, d.y],
      [hx, p.y],
      [hx, p.y],
      [p.x, p.y],
    ]
  }

  function linkId(...args) {
    return args.map(d => d.data.id).sort().join(", ")  // make unique id
  }

  function otherParent(child, p1, data) {
    const condition = d0 => (d0.data.id !== p1.data.id) && ((d0.data.id === child.data.rels.mother) || (d0.data.id === child.data.rels.father));
    return getRel(p1, data, condition)
  }

  // if there is overlapping of personas in different branches of same family tree, return the closest one
  function getRel(d, data, condition) {
    const rels = data.filter(condition);
    const dist_xy = (a, b) => Math.sqrt(Math.pow(a.x - b.x, 2) + Math.pow(a.y - b.y, 2));
    if (rels.length > 1) return rels.sort((d0, d1) => dist_xy(d0, d) - dist_xy(d1, d))[0]
    else return rels[0]
  }
}

function pathToMain(cards, links, datum, main_datum) {
  const is_ancestry = datum.is_ancestry;
  const links_data = links.data();
  let links_node_to_main = [];
  let cards_node_to_main = [];

  if (is_ancestry) {
    const links_to_main = [];

    let parent = datum;
    let itteration1 = 0;
    while (parent !== main_datum.data && itteration1 < 100) {
      itteration1++;  // to prevent infinite loop
      const spouse_link = links_data.find(d => d.spouse === true && (d.source === parent || d.target === parent));
      if (spouse_link) {
        const child_link = links_data.find(d => Array.isArray(d.target) && d.target.includes(spouse_link.source) && d.target.includes(spouse_link.target));
        if (!child_link) break
        links_to_main.push(spouse_link);
        links_to_main.push(child_link);
        parent = child_link.source;
      } else {
        // single parent
        const child_link = links_data.find(d => Array.isArray(d.target) && d.target.includes(parent));
        if (!child_link) break
        links_to_main.push(child_link);
        parent = child_link.source;
      }
    }
    links.each(function(d) {
      if (links_to_main.includes(d)) {
        links_node_to_main.push({link: d, node: this});
      }
    });

    const cards_to_main = getCardsToMain(datum, links_to_main);
    cards.each(function(d) {
      if (cards_to_main.includes(d)) {
        cards_node_to_main.push({card: d, node: this});
      }
    });
  } else if (datum.spouse && datum.spouse.data === main_datum.data) {
    links.each(function(d) {
      if (d.target === datum) links_node_to_main.push({link: d, node: this});
    });
    const cards_to_main = [main_datum, datum];
    cards.each(function(d) {
      if (cards_to_main.includes(d)) {
        cards_node_to_main.push({card: d, node: this});
      }
    });
  } else {
    let links_to_main = [];

    let child = datum;
    let itteration1 = 0;
    while (child !== main_datum.data && itteration1 < 100) {
      itteration1++;  // to prevent infinite loop
      const child_link = links_data.find(d => d.target === child && Array.isArray(d.source));
      if (child_link) {
        const spouse_link = links_data.find(d => d.spouse === true && sameArray([d.source, d.target], child_link.source));
        links_to_main.push(child_link);
        links_to_main.push(spouse_link);
        if (spouse_link) child = spouse_link.source;
        else child = child_link.source[0];
      } else {
        const spouse_link = links_data.find(d => d.target === child && !Array.isArray(d.source));  // spouse link
        if (!spouse_link) break
        links_to_main.push(spouse_link);
        child = spouse_link.source;
      }
    }

    links.each(function(d) {
      if (links_to_main.includes(d)) {
        links_node_to_main.push({link: d, node: this});
      }
    });

    const cards_to_main = getCardsToMain(main_datum, links_to_main);
    cards.each(function(d) {
      if (cards_to_main.includes(d)) {
        cards_node_to_main.push({card: d, node: this});
      }
    });
  }
  return [cards_node_to_main, links_node_to_main]

  function sameArray(arr1, arr2) {
    return arr1.every(d1 => arr2.some(d2 => d1 === d2))
  }

  function getCardsToMain(first_parent, links_to_main) {
    const all_cards = links_to_main.filter(d => d).reduce((acc, d) => {
      if (Array.isArray(d.target)) acc.push(...d.target);
      else acc.push(d.target);
      if (Array.isArray(d.source)) acc.push(...d.source);
      else acc.push(d.source);
      return acc
    }, []);

    const cards_to_main = [main_datum, datum];
    getChildren(first_parent);
    return cards_to_main

    function getChildren(d) {
      if (d.data.rels.children) {
        d.data.rels.children.forEach(child_id => {
          const child = all_cards.find(d0 => d0.data.id === child_id);
          if (child) {
            cards_to_main.push(child);
            getChildren(child);
          }
        });
      }
    }
  }
}

function createPath(d, is_) {
  const line = d3.line().curve(d3.curveMonotoneY),
    lineCurve = d3.line().curve(d3.curveBasis),
    path_data = is_ ? d._d() : d.d;

  if (!d.curve) return line(path_data)
  else if (d.curve === true) return lineCurve(path_data)
}

function updateLinks(svg, tree, props={}) {
  const links_data_dct = tree.data.reduce((acc, d) => {
    createLinks({d, tree:tree.data, is_horizontal: tree.is_horizontal}).forEach(l => acc[l.id] = l);
    return acc
  }, {});
  const links_data = Object.values(links_data_dct);
  const link = d3.select(svg).select(".links_view").selectAll("path.link").data(links_data, d => d.id);
  const link_exit = link.exit();
  const link_enter = link.enter().append("path").attr("class", "link");
  const link_update = link_enter.merge(link);

  link_exit.each(linkExit);
  link_enter.each(linkEnter);
  link_update.each(linkUpdate);

  function linkEnter(d) {
    d3.select(this).attr("fill", "none").attr("stroke", "#fff").attr("stroke-width", 1).style("opacity", 0)
      .attr("d", createPath(d, true));
  }

  function linkUpdate(d) {
    const path = d3.select(this);
    const delay = props.initial ? calculateDelay(tree, d, props.transition_time) : 0;
    path.transition('path').duration(props.transition_time).delay(delay).attr("d", createPath(d)).style("opacity", 1);
  }

  function linkExit(d) {
    const path = d3.select(this);
    path.transition('op').duration(800).style("opacity", 0);
    path.transition('path').duration(props.transition_time).attr("d", createPath(d, true))
      .on("end", () => path.remove());
  }

}

function updateCards(svg, tree, Card, props={}) {
  const card = d3.select(svg).select(".cards_view").selectAll("g.card_cont").data(tree.data, d => d.data.id),
    card_exit = card.exit(),
    card_enter = card.enter().append("g").attr("class", "card_cont"),
    card_update = card_enter.merge(card);

  card_exit.each(d => calculateEnterAndExitPositions(d, false, true));
  card_enter.each(d => calculateEnterAndExitPositions(d, true, false));

  card_exit.each(cardExit);
  card.each(cardUpdateNoEnter);
  card_enter.each(cardEnter);
  card_update.each(cardUpdate);

  function cardEnter(d) {
    d3.select(this)
      .attr("transform", `translate(${d._x}, ${d._y})`)
      .style("opacity", 0);

    Card.call(this, d);
  }

  function cardUpdateNoEnter(d) {}

  function cardUpdate(d) {
    Card.call(this, d);
    const delay = props.initial ? calculateDelay(tree, d, props.transition_time) : 0;
    d3.select(this).transition().duration(props.transition_time).delay(delay).attr("transform", `translate(${d.x}, ${d.y})`).style("opacity", 1);
  }

  function cardExit(d) {
    const g = d3.select(this);
    g.transition().duration(props.transition_time).style("opacity", 0).attr("transform", `translate(${d._x}, ${d._y})`)
      .on("end", () => g.remove());
  }
}

function updateCardsHtml(div, tree, Card, props={}) {
  const card = d3.select(div).select(".cards_view").selectAll("div.card_cont").data(tree.data, d => d.data.id),
    card_exit = card.exit(),
    card_enter = card.enter().append("div").attr("class", "card_cont").style('pointer-events', 'none'),
    card_update = card_enter.merge(card);

  card_exit.each(d => calculateEnterAndExitPositions(d, false, true));
  card_enter.each(d => calculateEnterAndExitPositions(d, true, false));

  card_exit.each(cardExit);
  card.each(cardUpdateNoEnter);
  card_enter.each(cardEnter);
  card_update.each(cardUpdate);

  function cardEnter(d) {
    d3.select(this)
      .style('position', 'absolute')
      .style('top', '0').style('left', '0')
      .style("transform", `translate(${d._x}px, ${d._y}px)`)
      .style("opacity", 0);

    Card.call(this, d);
  }

  function cardUpdateNoEnter(d) {}

  function cardUpdate(d) {
    Card.call(this, d);
    const delay = props.initial ? calculateDelay(tree, d, props.transition_time) : 0;
    d3.select(this).transition().duration(props.transition_time).delay(delay).style("transform", `translate(${d.x}px, ${d.y}px)`).style("opacity", 1);
  }

  function cardExit(d) {
    const g = d3.select(this);
    g.transition().duration(props.transition_time).style("opacity", 0).style("transform", `translate(${d._x}px, ${d._y}px)`)
      .on("end", () => g.remove());
  }
}

function assignUniqueIdToTreeData(div, tree_data) {
  const card = d3.select(div).selectAll("div.card_cont_2fake").data(tree_data, d => d.data.id);  // how this doesn't break if there is multiple cards with the same id?
  const card_exit = card.exit();
  const card_enter = card.enter().append("div").attr("class", "card_cont_2fake").style('display', 'none').attr("data-id", () => Math.random());
  const card_update = card_enter.merge(card);

  card_exit.each(cardExit);
  card_enter.each(cardEnter);
  card_update.each(cardUpdate);

  function cardEnter(d) {
    d.unique_id = d3.select(this).attr("data-id");
  }

  function cardUpdate(d) {
    d.unique_id = d3.select(this).attr("data-id");
  }

  function cardExit(d) {
    d.unique_id = d3.select(this).attr("data-id");
    d3.select(this).remove();
  }
}

function setupHtmlSvg(getHtmlSvg) {
  d3.select(getHtmlSvg()).append("div").attr("class", "cards_view_fake").style('display', 'none');  // important for handling data
}

function getCardsViewFake(getHtmlSvg) {
  return d3.select(getHtmlSvg()).select("div.cards_view_fake").node()
}

function onZoomSetup(getSvgView, getHtmlView) {
  return function onZoom(e) {
    const t = e.transform;
  
    d3.select(getSvgView()).style('transform', `translate(${t.x}px, ${t.y}px) scale(${t.k}) `);
    d3.select(getHtmlView()).style('transform', `translate(${t.x}px, ${t.y}px) scale(${t.k}) `);
  }
}

function setupReactiveTreeData(getHtmlSvg) {
  let tree_data = [];

  return function getReactiveTreeData(new_tree_data) {
    const tree_data_exit = getTreeDataExit(new_tree_data, tree_data);
    tree_data = [...new_tree_data, ...tree_data_exit];
    assignUniqueIdToTreeData(getCardsViewFake(getHtmlSvg), tree_data);
    return tree_data
  }
}

function createHtmlSvg(cont) {
  const f3Canvas = d3.select(cont).select('#f3Canvas');
  const cardHtml = f3Canvas.append('div').attr('id', 'htmlSvg')
    .attr('style', 'position: absolute; width: 100%; height: 100%; z-index: 2; top: 0; left: 0');
  cardHtml.append('div').attr('class', 'cards_view').style('transform-origin', '0 0');
  setupHtmlSvg(() => cardHtml.node());

  return cardHtml.node()
}

function getTreeDataExit(new_tree_data, old_tree_data) {
  if (old_tree_data.length > 0) {
    return old_tree_data.filter(d => !new_tree_data.find(t => t.data.id === d.data.id))
  } else {
    return []
  }
}

function getUniqueId(d) {
  return d.unique_id
}

var htmlHandlers = /*#__PURE__*/Object.freeze({
__proto__: null,
assignUniqueIdToTreeData: assignUniqueIdToTreeData,
setupHtmlSvg: setupHtmlSvg,
getCardsViewFake: getCardsViewFake,
onZoomSetup: onZoomSetup,
setupReactiveTreeData: setupReactiveTreeData,
createHtmlSvg: createHtmlSvg,
getUniqueId: getUniqueId
});

function updateCardsComponent(div, tree, Card, props={}) {
  const card = d3.select(getCardsViewFake(() => div)).selectAll("div.card_cont_fake").data(tree.data, d => d.data.id),
    card_exit = card.exit(),
    card_enter = card.enter().append("div").attr("class", "card_cont_fake").style('display', 'none'),
    card_update = card_enter.merge(card);

  card_exit.each(d => calculateEnterAndExitPositions(d, false, true));
  card_enter.each(d => calculateEnterAndExitPositions(d, true, false));

  card_exit.each(cardExit);
  card.each(cardUpdateNoEnter);
  card_enter.each(cardEnter);
  card_update.each(cardUpdate);

  function cardEnter(d) {
    const card_element = d3.select(Card(d));

    card_element
      .style('position', 'absolute')
      .style('top', '0').style('left', '0').style("opacity", 0)
      .style("transform", `translate(${d._x}px, ${d._y}px)`);
  }

  function cardUpdateNoEnter(d) {}

  function cardUpdate(d) {
    const card_element = d3.select(Card(d));
    const delay = props.initial ? calculateDelay(tree, d, props.transition_time) : 0;
    card_element.transition().duration(props.transition_time).delay(delay).style("transform", `translate(${d.x}px, ${d.y}px)`).style("opacity", 1);
  }

  function cardExit(d) {
    const card_element = d3.select(Card(d));
    const g = d3.select(this);
    card_element.transition().duration(props.transition_time).style("opacity", 0).style("transform", `translate(${d._x}px, ${d._y}px)`)
      .on("end", () => g.remove()); // remove the card_cont_fake
  }
}

function view(tree, svg, Card, props={}) {

  props.initial = props.hasOwnProperty('initial') ? props.initial : !d3.select(svg.parentNode).select('.card_cont').node();
  props.transition_time = props.hasOwnProperty('transition_time') ? props.transition_time : 2000;
  if (props.cardComponent) updateCardsComponent(props.cardComponent, tree, Card, props);
  else if (props.cardHtml) updateCardsHtml(props.cardHtml, tree, Card, props);
  else updateCards(svg, tree, Card, props);
  updateLinks(svg, tree, props);

  const tree_position = props.tree_position || 'fit';
  if (props.initial) treeFit({svg, svg_dim: svg.getBoundingClientRect(), tree_dim: tree.dim, transition_time: 0});
  else if (tree_position === 'fit') treeFit({svg, svg_dim: svg.getBoundingClientRect(), tree_dim: tree.dim, transition_time: props.transition_time});
  else if (tree_position === 'main_to_middle') cardToMiddle({datum: tree.data[0], svg, svg_dim: svg.getBoundingClientRect(), scale: props.scale, transition_time: props.transition_time});
  else ;

  return true
}

function calculateDelay(tree, d, transition_time) {
  const delay_level = transition_time*.4,
    ancestry_levels = Math.max(...tree.data.map(d=>d.is_ancestry ? d.depth : 0));
  let delay = d.depth*delay_level;
  if ((d.depth !== 0 || !!d.spouse) && !d.is_ancestry) {
    delay+=(ancestry_levels)*delay_level;  // after ancestry
    if (d.spouse) delay+=delay_level;  // spouse after bloodline
    delay+=(d.depth)*delay_level;  // double the delay for each level because of additional spouse delay
  }
  return delay
}

function createSvg(cont, props={}) {
  const svg_dim = cont.getBoundingClientRect();
  const svg_html = (`
    <svg class="main_svg">
      <rect width="${svg_dim.width}" height="${svg_dim.height}" fill="transparent" />
      <g class="view">
        <g class="links_view"></g>
        <g class="cards_view"></g>
      </g>
      <g style="transform: translate(100%, 100%)">
        <g class="fit_screen_icon cursor-pointer" style="transform: translate(-50px, -50px); display: none">
          <rect width="27" height="27" stroke-dasharray="${27/2}" stroke-dashoffset="${27/4}" 
            style="stroke:#fff;stroke-width:4px;fill:transparent;"/>
          <circle r="5" cx="${27/2}" cy="${27/2}" style="fill:#fff" />          
        </g>
      </g>
    </svg>
  `);

  const f3Canvas = getOrCreateF3Canvas(cont);

  const temp_div = d3.create('div').node();
  temp_div.innerHTML = svg_html;
  const svg = temp_div.querySelector('svg');
  f3Canvas.appendChild(svg);

  cont.appendChild(f3Canvas);

  setupZoom(f3Canvas, props);

  return svg

  function getOrCreateF3Canvas(cont) {
    let f3Canvas = cont.querySelector('#f3Canvas');
    if (!f3Canvas) {
      f3Canvas = d3.create('div').attr('id', 'f3Canvas').attr('style', 'position: relative; overflow: hidden; width: 100%; height: 100%;').node();
    }
    return f3Canvas
  }
}

function setupZoom(el, props={}) {
  if (el.__zoom) return
  const view = el.querySelector('.view'),
    zoom = d3.zoom().on("zoom", (props.onZoom || zoomed));

  d3.select(el).call(zoom);
  el.__zoomObj = zoom;

  if (props.zoom_polite) zoom.filter(zoomFilter);

  function zoomed(e) {
    d3.select(view).attr("transform", e.transform);
  }

  function zoomFilter(e) {
    if (e.type === "wheel" && !e.ctrlKey) return false
    else if (e.touches && e.touches.length < 2) return false
    else return true
  }
}

function cardChangeMain(store, {d}) {
  toggleAllRels(store.getTree().data, false);
  store.updateMainId(d.data.id);
  store.updateTree({tree_position: store.state.tree_fit_on_change});
  return true
}

function cardEdit(store, {d, cardEditForm}) {
  const datum = d.data,
    postSubmit = (props) => {
      if (datum.to_add) moveToAddToAdded(datum, store.getData());
      if (props && props.delete) {
        if (datum.main) store.updateMainId(null);
        deletePerson(datum, store.getData());
      }
      store.updateTree();
    };
  cardEditForm({datum, postSubmit, store});
}

function cardShowHideRels(store, {d}) {
  d.data.hide_rels = !d.data.hide_rels;
  toggleRels(d, d.data.hide_rels);
  store.updateTree({tree_position: store.state.tree_fit_on_change});
}

function userIcon() {
  return (`
    <g data-icon="user">
      ${bgCircle()}
      <path d="M12,4A4,4 0 0,1 16,8A4,4 0 0,1 12,12A4,4 0 0,1 8,8A4,4 0 0,1 12,4M12,14C16.42,14 20,15.79 20,18V20H4V18C4,15.79 7.58,14 12,14Z" />
    </g>
  `)
}

function userEditIcon() {
  return (`
    <g data-icon="user-edit">
      ${bgCircle()}
      <path d="M21.7,13.35L20.7,14.35L18.65,12.3L19.65,11.3C19.86,11.09 20.21,11.09 20.42,11.3L21.7,12.58C21.91,
      12.79 21.91,13.14 21.7,13.35M12,18.94L18.06,12.88L20.11,14.93L14.06,21H12V18.94M12,14C7.58,14 4,15.79 4,
      18V20H10V18.11L14,14.11C13.34,14.03 12.67,14 12,14M12,4A4,4 0 0,0 8,8A4,4 0 0,0 12,12A4,4 0 0,0 16,8A4,4 0 0,0 12,4Z" />
    </g>
  `)
}

function userPlusIcon() {
  return (`
    <g data-icon="user-plus">
      ${bgCircle()}
      <path d="M15,14C12.33,14 7,15.33 7,18V20H23V18C23,15.33 17.67,14 15,14M6,10V7H4V10H1V12H4V15H6V12H9V10M15,12A4,4 0 0,0 19,8A4,4 0 0,0 15,4A4,4 0 0,0 11,8A4,4 0 0,0 15,12Z" />
    </g>
  `)
}

function userPlusCloseIcon() {
  return (`
    <g data-icon="user-plus-close">
      ${bgCircle()}
      <path d="M15,14C12.33,14 7,15.33 7,18V20H23V18C23,15.33 17.67,14 15,14M6,10V7H4V10H1V12H4V15H6V12H9V10M15,12A4,4 0 0,0 19,8A4,4 0 0,0 15,4A4,4 0 0,0 11,8A4,4 0 0,0 15,12Z" />
      <line x1="3" y1="3" x2="24" y2="24" stroke="currentColor" stroke-width="2" />
    </g>
  `)
}

function plusIcon() {
  return (`
    <g data-icon="plus">
      ${bgCircle()}
      <path d="M19,13H13V19H11V13H5V11H11V5H13V11H19V13Z" />
    </g>
  `)
}

function pencilIcon() {
  return (`
    <g data-icon="pencil">
      ${bgCircle()}
      <path d="M20.71,7.04C21.1,6.65 21.1,6 20.71,5.63L18.37,3.29C18,2.9 17.35,2.9 16.96,3.29L15.12,5.12L18.87,8.87M3,17.25V21H6.75L17.81,9.93L14.06,6.18L3,17.25Z" />
    </g>
  `)
}

function pencilOffIcon() {
  return (`
    <g data-icon="pencil-off">
      ${bgCircle()}
      <path d="M18.66,2C18.4,2 18.16,2.09 17.97,2.28L16.13,4.13L19.88,7.88L21.72,6.03C22.11,5.64 22.11,5 21.72,4.63L19.38,2.28C19.18,2.09 18.91,2 18.66,2M3.28,4L2,5.28L8.5,11.75L4,16.25V20H7.75L12.25,15.5L18.72,22L20,20.72L13.5,14.25L9.75,10.5L3.28,4M15.06,5.19L11.03,9.22L14.78,12.97L18.81,8.94L15.06,5.19Z" />
    </g>
  `)
}

function trashIcon() {
  return (`
    <g data-icon="trash">
      ${bgCircle()}
      <path d="M6,19A2,2 0 0,0 8,21H16A2,2 0 0,0 18,19V7H6V19M8,9H16V19H8V9M15.5,4L14.5,3H9.5L8.5,4H5V6H19V4H15.5Z" />
    </g>
  `)
}

function historyBackIcon() {
  return (`
    <g data-icon="history-back">
      ${bgCircle()}
      <path d="M20 13.5C20 17.09 17.09 20 13.5 20H6V18H13.5C16 18 18 16 18 13.5S16 9 13.5 9H7.83L10.91 12.09L9.5 13.5L4 8L9.5 2.5L10.92 3.91L7.83 7H13.5C17.09 7 20 9.91 20 13.5Z" />
    </g>
  `)
}

function historyForwardIcon() {
  return (`
    <g data-icon="history-forward">
      ${bgCircle()}
      <path d="M10.5 18H18V20H10.5C6.91 20 4 17.09 4 13.5S6.91 7 10.5 7H16.17L13.08 3.91L14.5 2.5L20 8L14.5 13.5L13.09 12.09L16.17 9H10.5C8 9 6 11 6 13.5S8 18 10.5 18Z" />
    </g>
  `)
}

function personIcon() {
  return (`
    <g data-icon="person">
      <path d="M256 288c79.5 0 144-64.5 144-144S335.5 0 256 0 112 
        64.5 112 144s64.5 144 144 144zm128 32h-55.1c-22.2 10.2-46.9 16-72.9 16s-50.6-5.8-72.9-16H128C57.3 320 0 377.3 
        0 448v16c0 26.5 21.5 48 48 48h416c26.5 0 48-21.5 48-48v-16c0-70.7-57.3-128-128-128z" />
    </g>
  `)
}

function miniTreeIcon() {
  return (`
    <g transform="translate(31,25)" data-icon="mini-tree">
      <rect x="-31" y="-25" width="72" height="15" fill="rgba(0,0,0,0)"></rect>
      <g>
        <rect x="-31" y="-25" width="72" height="15" fill="rgba(0,0,0,0)"></rect>
        <line y2="-17.5" stroke="#fff" />
        <line x1="-20" x2="20" y1="-17.5" y2="-17.5" stroke="#fff" />
        <rect x="-31" y="-25" width="25" height="15" rx="5" ry="5" class="card-male" />
        <rect x="6" y="-25" width="25" height="15" rx="5" ry="5" class="card-female" />
      </g>
    </g>
  `)
}

function userSvgIcon() { return svgWrapper(userIcon()) }
function userEditSvgIcon() { return svgWrapper(userEditIcon()) }
function userPlusSvgIcon() { return svgWrapper(userPlusIcon()) }
function userPlusCloseSvgIcon() { return svgWrapper(userPlusCloseIcon()) }
function plusSvgIcon() { return svgWrapper(plusIcon()) }
function pencilSvgIcon() { return svgWrapper(pencilIcon()) }
function pencilOffSvgIcon() { return svgWrapper(pencilOffIcon()) }
function trashSvgIcon() { return svgWrapper(trashIcon()) }
function historyBackSvgIcon() { return svgWrapper(historyBackIcon()) }
function historyForwardSvgIcon() { return svgWrapper(historyForwardIcon()) }
function personSvgIcon() { return svgWrapper(personIcon(), '0 0 512 512') }
function miniTreeSvgIcon() { return svgWrapper(miniTreeIcon(), '0 0 72 25') }

function svgWrapper(icon, viewBox='0 0 24 24') {
  const match = icon.match(/data-icon="([^"]+)"/);
  const dataIcon = match ? `data-icon="${match[1]}"` : '';
  
  return (`
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="${viewBox}" style="fill: currentColor" ${dataIcon}>
      ${icon}
    </svg>
  `)
}

function bgCircle() {
  return (`
    <circle r="12" cx="12" cy="12" style="fill: rgba(0,0,0,0)" />
  `)
}

var icons = /*#__PURE__*/Object.freeze({
__proto__: null,
userIcon: userIcon,
userEditIcon: userEditIcon,
userPlusIcon: userPlusIcon,
userPlusCloseIcon: userPlusCloseIcon,
plusIcon: plusIcon,
pencilIcon: pencilIcon,
pencilOffIcon: pencilOffIcon,
trashIcon: trashIcon,
historyBackIcon: historyBackIcon,
historyForwardIcon: historyForwardIcon,
personIcon: personIcon,
miniTreeIcon: miniTreeIcon,
userSvgIcon: userSvgIcon,
userEditSvgIcon: userEditSvgIcon,
userPlusSvgIcon: userPlusSvgIcon,
userPlusCloseSvgIcon: userPlusCloseSvgIcon,
plusSvgIcon: plusSvgIcon,
pencilSvgIcon: pencilSvgIcon,
pencilOffSvgIcon: pencilOffSvgIcon,
trashSvgIcon: trashSvgIcon,
historyBackSvgIcon: historyBackSvgIcon,
historyForwardSvgIcon: historyForwardSvgIcon,
personSvgIcon: personSvgIcon,
miniTreeSvgIcon: miniTreeSvgIcon
});

function formInfoSetup(form_creator, closeCallback) {
  const formContainer = document.createElement('div');
  update();
  return formContainer

  function update() {
    const formHtml = getHtml(form_creator);

    formContainer.innerHTML = formHtml;
  
    setupEventListeners();

    return formContainer
  }

  function setupEventListeners() {
    const form = formContainer.querySelector('form');
    form.addEventListener('submit', form_creator.onSubmit);

    const cancel_btn = form.querySelector('.f3-cancel-btn');
    cancel_btn.addEventListener('click', onCancel);

    const edit_btn = form.querySelector('.f3-edit-btn');
    if (edit_btn) edit_btn.addEventListener('click', onEdit);

    const delete_btn = form.querySelector('.f3-delete-btn');
    if (delete_btn && form_creator.onDelete) {
      delete_btn.addEventListener('click', form_creator.onDelete);
    }

    const add_relative_btn = form.querySelector('.f3-add-relative-btn');
    if (add_relative_btn && form_creator.addRelative) {
      add_relative_btn.addEventListener('click', () => {
        if (form_creator.addRelativeActive) form_creator.addRelativeCancel();
        else form_creator.addRelative();
        form_creator.addRelativeActive = !form_creator.addRelativeActive;
        update();
      });
    }

    const close_btn = form.querySelector('.f3-close-btn');
    close_btn.addEventListener('click', closeCallback);

    if (form_creator.other_parent_field) {
      cancel_btn.style.display = 'none';
    }

    function onCancel() {
      form_creator.editable = false;
      if (form_creator.onCancel) form_creator.onCancel();
      update();
    }

    function onEdit() {
      form_creator.editable = !form_creator.editable;
      update();
    }
  }
}

 function getHtml(form_creator) {
  return (` 
    <form id="familyForm" class="f3-form ${form_creator.editable ? '' : 'non-editable'}">
      ${closeBtn()}
      ${form_creator.title ? `<h3 class="f3-form-title">${form_creator.title}</h3>` : ''}
      <div style="text-align: right; display: ${form_creator.new_rel ? 'none' : 'block'}">
        ${form_creator.addRelative && !form_creator.no_edit ? addRelativeBtn() : ''}
        ${form_creator.no_edit ? spaceDiv() : editBtn()}
      </div>
      ${genderRadio()}

      ${fields()}

      ${form_creator.other_parent_field ? otherParentField() : ''}

      ${form_creator.onDelete ? deleteBtn() : ''}
      
      <div class="f3-form-buttons">
        <button type="button" class="f3-cancel-btn">Cancel</button>
        <button type="submit">Submit</button>
      </div>
    </form>
  `)

  function deleteBtn() {
    return (`
      <div>
        <button type="button" class="f3-delete-btn" ${form_creator.can_delete ? '' : 'disabled'}>
          Delete
        </button>
      </div>
    `)
  }

  function addRelativeBtn() {
    return (`
      <span class="f3-add-relative-btn">
        ${form_creator.addRelativeActive ? userPlusCloseSvgIcon() : userPlusSvgIcon()}
      </span>
    `)
  }

  function editBtn() {
    return (`
      <span class="f3-edit-btn">
        ${form_creator.editable ? pencilOffSvgIcon() : pencilSvgIcon()}
      </span>
    `)
  }

  function genderRadio() {
    if (!form_creator.editable) return ''
    return (`
      <div class="f3-radio-group">
        ${form_creator.gender_field.options.map(option => (`
          <label>
            <input type="radio" name="${form_creator.gender_field.id}" 
              value="${option.value}" 
              ${option.value === form_creator.gender_field.initial_value ? 'checked' : ''}
            >
            ${option.label}
          </label>
        `)).join('')}
      </div>
    `)
  }

  function fields() {
    if (!form_creator.editable) return infoField()
    return form_creator.fields.map(field => (`
      ${field.type === 'text' ? `
        <div class="f3-form-field">
          <label>${field.label}</label>
          <input type="${field.type}" 
            name="${field.id}" 
            value="${field.initial_value || ''}"
            placeholder="${field.label}">
        </div>
      ` : field.type === 'textarea' ? `
        <div class="f3-form-field">
          <label>${field.label}</label>
          <textarea name="${field.id}" 
            placeholder="${field.label}">${field.initial_value || ''}</textarea>
        </div>
      ` : ''}
    `)).join('')

    function infoField() {
      return form_creator.fields.map(field => (`
        <div class="f3-info-field">
          <span class="f3-info-field-label">${field.label}</span>
          <span class="f3-info-field-value">${field.initial_value || ''}</span>
        </div>
      `)).join('')
    }
  }

  function otherParentField() {
    return (`
      <div class="f3-form-field">
        <label>${form_creator.other_parent_field.label}</label>
        <select name="${form_creator.other_parent_field.id}">
          ${form_creator.other_parent_field.options.map(option => `
            <option value="${option.value}" 
              ${option.value === form_creator.other_parent_field.initial_value ? 'selected' : ''}>
              ${option.label}
            </option>
          `).join('')}
        </select>
      </div>
    `)
  }

  function closeBtn() {
    return (`
      <span class="f3-close-btn">
        ×
      </span>
    `)
  }

  function spaceDiv() {
    return `<div style="height: 24px;"></div>`
  }
}

function createHistory(store, getStoreData, onUpdate) {
  let history = [];
  let history_index = -1;
  
  return {
    changed,
    back,
    forward,
    canForward,
    canBack
  }

  function changed() {
    if (history_index < history.length - 1) history = history.slice(0, history_index);
    const clean_data = JSON.parse(cleanupDataJson(JSON.stringify(getStoreData())));
    clean_data.main_id = store.getMainId();
    history.push(clean_data);
    history_index++;
  }

  function back() {
    if (!canBack()) return
    history_index--;
    updateData(history[history_index]);
  }

  function forward() {
    if (!canForward()) return
    history_index++;
    updateData(history[history_index]);
  }

  function canForward() {
    return history_index < history.length - 1
  }

  function canBack() {
    return history_index > 0
  }

  function updateData(data) {
    store.updateMainId(data.main_id);
    store.updateData(data);
    onUpdate();
  }
}

function createHistoryControls(cont, history, onUpdate=()=>{}) {
  const history_controls = d3.select(cont).append("div").attr("class", "f3-history-controls");
  const back_btn = history_controls.append("button").attr("class", "f3-back-button").on("click", () => {
    history.back();
    updateButtons();
    onUpdate();
  });
  const forward_btn = history_controls.append("button").attr("class", "f3-forward-button").on("click", () => {
    history.forward();
    updateButtons();
    onUpdate();
  });

  back_btn.html(historyBackSvgIcon());
  forward_btn.html(historyForwardSvgIcon());

  return {
    back_btn: back_btn.node(),
    forward_btn: forward_btn.node(),
    updateButtons,
    destroy
  }

  function updateButtons() {
    back_btn.classed("disabled", !history.canBack());
    forward_btn.classed("disabled", !history.canForward());
    history_controls.style("display", !history.canBack() && !history.canForward() ? "none" : null);
  }

  function destroy() {
    history = null;
    d3.select(cont).select('.f3-history-controls').remove();
  }
}

var handlers = /*#__PURE__*/Object.freeze({
__proto__: null,
manualZoom: manualZoom,
isAllRelativeDisplayed: isAllRelativeDisplayed,
cardChangeMain: cardChangeMain,
cardEdit: cardEdit,
cardShowHideRels: cardShowHideRels,
handleRelsOfNewDatum: handleRelsOfNewDatum,
handleNewRel: handleNewRel,
createNewPerson: createNewPerson,
createNewPersonWithGenderFromRel: createNewPersonWithGenderFromRel,
addNewPerson: addNewPerson,
createTreeDataWithMainNode: createTreeDataWithMainNode,
addNewPersonAndHandleRels: addNewPersonAndHandleRels,
checkIfRelativesConnectedWithoutPerson: checkIfRelativesConnectedWithoutPerson,
createForm: createForm,
moveToAddToAdded: moveToAddToAdded,
removeToAdd: removeToAdd,
deletePerson: deletePerson,
cleanupDataJson: cleanupDataJson,
removeToAddFromData: removeToAddFromData,
formInfoSetup: formInfoSetup,
createHistory: createHistory,
createHistoryControls: createHistoryControls,
treeFit: treeFit,
calculateTreeFit: calculateTreeFit,
cardToMiddle: cardToMiddle
});

function CardBody({d,card_dim,card_display}) {
  return {template: (`
    <g class="card-body">
      <rect width="${card_dim.w}" height="${card_dim.h}" class="card-body-rect" />
      ${CardText({d,card_dim,card_display}).template}
    </g>
  `)
  }
}

function CardText({d,card_dim,card_display}) {
  return {template: (`
    <g>
      <g class="card-text" clip-path="url(#card_text_clip)">
        <g transform="translate(${card_dim.text_x}, ${card_dim.text_y})">
          <text>
            ${Array.isArray(card_display) ? card_display.map(cd => `<tspan x="${0}" dy="${14}">${cd(d.data)}</tspan>`).join('\n') : card_display(d.data)}
          </text>
        </g>
      </g>
      <rect width="${card_dim.w-10}" height="${card_dim.h}" style="mask: url(#fade)" class="text-overflow-mask" /> 
    </g>
  `)
  }
}

function CardBodyAddNew({d,card_dim,card_add,label}) {
  return {template: (`
    <g class="card-body ${card_add ? 'card_add' : 'card-unknown'}">
      <rect class="card-body-rect" width="${card_dim.w}" height="${card_dim.h}" fill="rgb(59, 85, 96)" />
      <text transform="translate(${card_dim.w/2}, ${card_dim.h/2})" text-anchor="middle" fill="#fff">
        <tspan font-size="18" dy="${8}">${label}</tspan>
      </text>
    </g>
  `)
  }
}

function CardBodyOutline({d,card_dim, is_new}) {
  return {template: (`
    <rect width="${card_dim.w}" height="${card_dim.h}" rx="4" ry="4" class="card-outline ${(d.data.main && !is_new) ? 'card-main-outline' : ''} ${is_new ? 'card-new-outline' : ''}" />
  `)
  }
}

function PencilIcon({d,card_dim,x,y}) {
  return ({template: (`
    <g transform="translate(${x || card_dim.w-20},${y || card_dim.h-20})scale(.6)" style="cursor: pointer" class="card_edit pencil_icon">
      <circle fill="rgba(0,0,0,0)" r="17" cx="8.5" cy="8.5" />
      <path fill="currentColor" transform="translate(-1.5, -1.5)"
         d="M19.082,2.123L17.749,0.79c-1.052-1.052-2.766-1.054-3.819,0L1.925,12.794c-0.06,0.06-0.104,0.135-0.127,0.216
          l-1.778,6.224c-0.05,0.175-0.001,0.363,0.127,0.491c0.095,0.095,0.223,0.146,0.354,0.146c0.046,0,0.092-0.006,0.137-0.02
          l6.224-1.778c0.082-0.023,0.156-0.066,0.216-0.127L19.082,5.942C20.134,4.89,20.134,3.176,19.082,2.123z M3.076,13.057l9.428-9.428
          l3.738,3.739l-9.428,9.428L3.076,13.057z M2.566,13.961l3.345,3.344l-4.683,1.339L2.566,13.961z M18.375,5.235L16.95,6.66
          l-3.738-3.739l1.425-1.425c0.664-0.663,1.741-0.664,2.405,0l1.333,1.333C19.038,3.493,19.038,4.572,18.375,5.235z"/>
    </g>
  `)})
}

function MiniTree({d,card_dim}) {
  return ({template: (`
    <g class="card_family_tree" style="cursor: pointer">
      <rect x="-31" y="-25" width="72" height="15" fill="rgba(0,0,0,0)"></rect>
      <g transform="translate(${card_dim.w*.8},6)scale(.9)">
        <rect x="-31" y="-25" width="72" height="15" fill="rgba(0,0,0,0)"></rect>
        <line y2="-17.5" stroke="#fff" />
        <line x1="-20" x2="20" y1="-17.5" y2="-17.5" stroke="#fff" />
        <rect x="-31" y="-25" width="25" height="15" rx="5" ry="5" class="card-male" />
        <rect x="6" y="-25" width="25" height="15" rx="5" ry="5" class="card-female" />
      </g>
    </g>
  `)})
}

function PlusIcon({d,card_dim,x,y}) {
  return ({template: (`
    <g class="card_add_relative">
      <g transform="translate(${x || card_dim.w/2},${y || card_dim.h})scale(.13)">
        <circle r="80" cx="40" cy="40" fill="rgba(0,0,0,0)" />
        <g transform="translate(-10, -8)">
          <line
            x1="10" x2="90" y1="50" y2="50"
            stroke="currentColor" stroke-width="15" stroke-linecap="round"
          />
          <line
            x1="50" x2="50" y1="10" y2="90"
            stroke="currentColor" stroke-width="15" stroke-linecap="round"
          />
        </g>
      </g>
    </g>
  `)})
}

function LinkBreakIcon({x,y,rt,closed}) {
  return ({template: (`
    <g style="
          transform: translate(-12.2px, -.5px);
          cursor: pointer;
        " 
        fill="currentColor" class="card_break_link${closed ? ' closed' : ''}"
      >
      <g style="transform: translate(${x}px,${y}px)scale(.02)rotate(${rt+'deg'})">
        <rect width="1000" height="700" y="150" style="opacity: 0" />
        <g class="link_upper">
          <g>
            <path d="M616.3,426.4c19,4.5,38.1-7.4,42.6-26.4c4.4-19-7.4-38-26.5-42.5L522.5,332c-18,11.1-53.9,33.4-53.9,33.4l80.4,18.6c-7.8,4.9-19.5,12.1-31.3,19.4L616.3,426.4L616.3,426.4z"/>
            <path d="M727.4,244.2c-50.2-11.6-100.3,3.3-135.7,35.4c28.6,22.6,64.5,30.2,116.4,51.3l141,32.6c23.9,5.6,56.6,47.2,51.1,71l-4.1,17c-5.6,23.7-47.3,56.4-71.2,51l-143.4-33.2c-66.8-8.6-104.1-16.6-132.9-7.5c17.4,44.9,55.9,80.8,106.5,92.4L800.9,588c81.3,18.8,162.3-31.5,181.2-112.4l4-17c18.8-81.1-31.7-161.8-112.9-180.6L727.4,244.2z"/>
          </g>
        </g>
        <g class="link_lower">
          <path d="M421.2,384.9l-128,127.6c-13.9,13.8-13.9,36.2,0,50s36.3,13.8,50.2,0.1l136.2-135.8v-36.7l-58.4,58.1V384.9L421.2,384.9z"/>
          <path d="M204.6,742.8c-17.4,17.3-63.3,17.2-80.6,0.1l-12.3-12.3c-17.3-17.3,0.6-81.2,17.9-98.5l100.2-99.9c12.5-14.9,45.8-40.8,66.1-103.7c-47.7-9.4-98.9,4.2-135.8,40.9L54.2,575c-58.9,58.8-58.9,154,0,212.8L66.6,800c58.9,58.8,154.5,58.8,213.4,0l105.8-105.6c38.4-38.3,51.3-91.9,39.7-141c-44,22.7-89,62.3-116,84.8L204.6,742.8z"/>
        </g>
        <g class="link_particles">
          <path d="M351.9,248.4l-26.5,63.4l80.6,30.1L351.9,248.4z"/>
          <path d="M529.3,208l-43,26.6l35.4,52.3L529.3,208z"/>
          <path d="M426.6,158.8l-44-2.9l61.7,134.6L426.6,158.8z"/>
        </g>
      </g>
    </g>
  `)})
}

function LinkBreakIconWrapper({d,card_dim}) {
  let g = "",
    r = d.data.rels, _r = d.data._rels || {},
    closed = d.data.hide_rels,
    areParents = r => r.father || r.mother,
    areChildren = r => r.children && r.children.length > 0;
  if ((d.is_ancestry || d.data.main) && (areParents(r) || areParents(_r))) {g+=LinkBreakIcon({x:card_dim.w/2,y:0, rt: -45, closed}).template;}
  if (!d.is_ancestry && d.added) {
    const sp = d.spouse, sp_r = sp.data.rels, _sp_r = sp.data._rels || {};
    if ((areChildren(r) || areChildren(_r)) && (areChildren(sp_r) || areChildren(_sp_r))) {
      g+=LinkBreakIcon({x:d.sx - d.x + card_dim.w/2 +24.4,y: (d.x !== d.sx ? card_dim.h/2 : card_dim.h)+1, rt: 135, closed}).template;
    }
  }
  return {template: g}
}

function CardImage({d, image, card_dim, maleIcon, femaleIcon}) {
  return ({template: (`
    <g style="transform: translate(${card_dim.img_x}px,${card_dim.img_y}px);" class="card_image" clip-path="url(#card_image_clip)">
      ${image 
        ? `<image href="${image}" height="${card_dim.img_h}" width="${card_dim.img_w}" preserveAspectRatio="xMidYMin slice" />`
        : (d.data.data.gender === "F" && !!femaleIcon) ? femaleIcon({card_dim}) 
        : (d.data.data.gender === "M" && !!maleIcon) ? maleIcon({card_dim}) 
        : GenderlessIcon()
      }      
    </g>
  `)})

  function GenderlessIcon() {
    return (`
      <g class="genderless-icon">
        <rect height="${card_dim.img_h}" width="${card_dim.img_w}" fill="rgb(59, 85, 96)" />
        <g transform="scale(${card_dim.img_w*0.001616})">
         <path transform="translate(50,40)" fill="lightgrey" d="M256 288c79.5 0 144-64.5 144-144S335.5 0 256 0 112 
            64.5 112 144s64.5 144 144 144zm128 32h-55.1c-22.2 10.2-46.9 16-72.9 16s-50.6-5.8-72.9-16H128C57.3 320 0 377.3 
            0 448v16c0 26.5 21.5 48 48 48h416c26.5 0 48-21.5 48-48v-16c0-70.7-57.3-128-128-128z" />
        </g>
      </g>
    `)
  }
}

function appendTemplate(template, parent, is_first) {
  const g = document.createElementNS("http://www.w3.org/2000/svg", 'g');
  g.innerHTML = template;

  if (is_first) parent.insertBefore(g, parent.firstChild);
  else parent.appendChild(g);
}

const CardElements = {
  miniTree,
  lineBreak,
  cardBody,
  cardImage,
  cardEdit: cardEditIcon,
  cardAdd: cardAddIcon,
};

function miniTree(d, props) {
  if (d.data.to_add) return
  const card_dim = props.card_dim;
  if (d.all_rels_displayed) return
  const g = d3.create('svg:g').html(MiniTree({d,card_dim}).template);
  g.on("click", function (e) {
    e.stopPropagation();
    if (props.onMiniTreeClick) props.onMiniTreeClick.call(this, e, d);
    else cardChangeMain(props.store, {d});
  });
  return g.node()
}

function lineBreak(d, props) {
  if (d.data.to_add) return
  const card_dim = props.card_dim;
  const g = d3.create('svg:g').html(LinkBreakIconWrapper({d,card_dim}).template);
  g.on("click", (e) => {e.stopPropagation();cardShowHideRels(props.store, {d});});
  return g.node()
}

function cardBody(d, props) {
  const unknown_lbl = props.cardEditForm ? 'ADD' : 'UNKNOWN';
  const card_dim = props.card_dim;

  let g;
  if (!d.data.to_add) {
    g = d3.create('svg:g').html(CardBody({d, card_dim, card_display: props.card_display}).template);
    g.on("click", function (e) {
      e.stopPropagation();
      if (props.onCardClick) props.onCardClick.call(this, e, d);
      else cardChangeMain(props.store, {d});
    });
  } else {
    g = d3.create('svg:g').html(CardBodyAddNew({d, card_dim, card_add: props.cardEditForm, label: unknown_lbl}).template);
    g.on("click", (e) => {e.stopPropagation();cardEdit(props.store, {d, cardEditForm: props.cardEditForm});});
  }
  return g.node()
}

function cardImage(d, props) {
  if (d.data.to_add) return
  const card_dim = props.card_dim;
  const g = d3.create('svg:g').html(CardImage({d, image: d.data.data.avatar || null, card_dim, maleIcon: null, femaleIcon: null}).template);
  return g.node()
}

function cardEditIcon(d, props) {
  if (d.data.to_add) return
  const card_dim = props.card_dim;
  const g = d3.create('svg:g').html(PencilIcon({card_dim, x: card_dim.w-46, y: card_dim.h-20}).template);
  g.on("click", (e) => {e.stopPropagation();cardEdit(props.store, {d, cardEditForm: props.cardEditForm});});

  return g.node()
}

function cardAddIcon(d, props) {
  if (d.data.to_add) return
  const card_dim = props.card_dim;
  const g = d3.create('svg:g').html(PlusIcon({card_dim, x: card_dim.w-26, y: card_dim.h-20}).template);
  g.on("click", (e) => {e.stopPropagation();props.addRelative({d});});

  return g.node()
}


function appendElement(el_maybe, parent, is_first) {
  if (!el_maybe) return
  if (is_first) parent.insertBefore(el_maybe, parent.firstChild);
  else parent.appendChild(el_maybe);
}

function setupCardSvgDefs(svg, card_dim) {
  if (svg.querySelector("defs#f3CardDef")) return
  svg.insertAdjacentHTML('afterbegin', (`
      <defs id="f3CardDef">
        <linearGradient id="fadeGrad">
          <stop offset="0.9" stop-color="white" stop-opacity="0"/>
          <stop offset=".91" stop-color="white" stop-opacity=".5"/>
          <stop offset="1" stop-color="white" stop-opacity="1"/>
        </linearGradient>
        <mask id="fade" maskContentUnits="objectBoundingBox"><rect width="1" height="1" fill="url(#fadeGrad)"/></mask>
        <clipPath id="card_clip"><path d="${curvedRectPath({w:card_dim.w, h:card_dim.h}, 5)}"></clipPath>
        <clipPath id="card_text_clip"><rect width="${card_dim.w-10}" height="${card_dim.h}"></rect></clipPath>
        <clipPath id="card_image_clip"><path d="M0,0 Q 0,0 0,0 H${card_dim.img_w} V${card_dim.img_h} H0 Q 0,${card_dim.img_h} 0,${card_dim.img_h} z"></clipPath>
        <clipPath id="card_image_clip_curved"><path d="${curvedRectPath({w: card_dim.img_w, h:card_dim.img_h}, 5, ['rx', 'ry'])}"></clipPath>
      </defs>
    `));

  function curvedRectPath(dim, curve, no_curve_corners) {
    const {w,h} = dim,
      c = curve,
      ncc = no_curve_corners || [],
      ncc_check = (corner) => ncc.includes(corner),
      lx = ncc_check('lx') ? `M0,0` : `M0,${c} Q 0,0 5,0`,
      rx = ncc_check('rx') ? `H${w}` : `H${w-c} Q ${w},0 ${w},5`,
      ry = ncc_check('ry') ? `V${h}` : `V${h-c} Q ${w},${h} ${w-c},${h}`,
      ly = ncc_check('ly') ? `H0` : `H${c} Q 0,${h} 0,${h-c}`;

    return (`${lx} ${rx} ${ry} ${ly} z`)
  }
}

function updateCardSvgDefs(svg, card_dim) {
  if (svg.querySelector("defs#f3CardDef")) {
    svg.querySelector("defs#f3CardDef").remove();
  }
  setupCardSvgDefs(svg, card_dim);
}

function Card(props) {
  props = setupProps(props);
  setupCardSvgDefs(props.svg, props.card_dim);

  return function (d) {
    const gender_class = d.data.data.gender === 'M' ? 'card-male' : d.data.data.gender === 'F' ? 'card-female' : 'card-genderless';
    const card_dim = props.card_dim;

    const card = d3.create('svg:g').attr('class', `card ${gender_class}`).attr('transform', `translate(${[-card_dim.w / 2, -card_dim.h / 2]})`);
    card.append('g').attr('class', 'card-inner').attr('clip-path', 'url(#card_clip)');

    this.innerHTML = '';
    this.appendChild(card.node());

    appendTemplate(CardBodyOutline({d,card_dim,is_new:d.data.to_add}).template, card.node(), true);
    appendElement(CardElements.cardBody(d, props), this.querySelector('.card-inner'));

    if (props.img) appendElement(CardElements.cardImage(d, props), this.querySelector('.card'));
    if (props.mini_tree) appendElement(CardElements.miniTree(d, props), this.querySelector('.card'), true);
    if (props.link_break) appendElement(CardElements.lineBreak(d, props), this.querySelector('.card'));

    if (props.cardEditForm) {
      appendElement(CardElements.cardEdit(d, props), this.querySelector('.card-inner'));
      appendElement(CardElements.cardAdd(d, props), this.querySelector('.card-inner'));
    }

    if (props.onCardUpdates) props.onCardUpdates.map(fn => fn.call(this, d));
    if (props.onCardUpdate) props.onCardUpdate.call(this, d);
  }

  function setupProps(props) {
    const default_props = {
      img: true,
      mini_tree: true,
      link_break: false,
      card_dim: {w:220,h:70,text_x:75,text_y:15,img_w:60,img_h:60,img_x:5,img_y:5}
    };
    if (!props) props = {};
    for (const k in default_props) {
      if (typeof props[k] === 'undefined') props[k] = default_props[k];
    }
    return props
  }
}

function CardHtml(props) {
  const cardInner = props.style === 'default' ? cardInnerDefault 
  : props.style === 'imageCircleRect' ? cardInnerImageCircleRect
  : props.style === 'imageCircle' ? cardInnerImageCircle 
  : props.style === 'imageRect' ? cardInnerImageRect
  : props.style === 'rect' ? cardInnerRect
  : cardInnerDefault;

  return function (d) {
    this.innerHTML = (`
    <div class="card ${getClassList(d).join(' ')}" data-id="${d.data.id}" style="transform: translate(-50%, -50%); pointer-events: auto;">
      ${props.mini_tree ? getMiniTree(d) : ''}
      ${cardInner(d)}
    </div>
    `);
    this.querySelector('.card').addEventListener('click', e => props.onCardClick(e, d));
    if (props.onCardUpdate) props.onCardUpdate.call(this, d);

    if (props.onCardMouseenter) d3.select(this).select('.card').on('mouseenter', e => props.onCardMouseenter(e, d));
    if (props.onCardMouseleave) d3.select(this).select('.card').on('mouseleave', e => props.onCardMouseleave(e, d));
  }

  function getCardInnerImageCircle(d) {
    return (`
    <div class="card-inner card-image-circle" ${getCardStyle()}>
      ${d.data.data.avatar ? `<img src="${d.data.data["avatar"]}" ${getCardImageStyle()}>` : noImageIcon(d)}
      <div class="card-label">${textDisplay(d)}</div>
    </div>
    `)
  }

  function getCardInnerImageRect(d) {
    return (`
    <div class="card-inner card-image-rect" ${getCardStyle()}>
      ${d.data.data.avatar ? `<img src="${d.data.data["avatar"]}" ${getCardImageStyle()}>` : noImageIcon(d)}
      <div class="card-label">${textDisplay(d)}</div>
    </div>
    `)
  }

  function getCardInnerRect(d) {
    return (`
    <div class="card-inner card-rect" ${getCardStyle()}>
      ${textDisplay(d)}
    </div>
    `)
  }

  function textDisplay(d) {
    if (d.data._new_rel_data) return newRelDataDisplay(d)
    if (d.data.to_add) return `<div>${props.empty_card_label || 'ADD'}</div>`
    return (`
      ${props.card_display.map(display => `<div>${display(d.data)}</div>`).join('')}
    `)
  }

  function newRelDataDisplay(d) {
    const attr_list = [];
    attr_list.push(`data-rel-type="${d.data._new_rel_data.rel_type}"`);
    if (['son', 'daughter'].includes(d.data._new_rel_data.rel_type)) attr_list.push(`data-other-parent-id="${d.data._new_rel_data.other_parent_id}"`);
    return `<div ${attr_list.join(' ')}>${d.data._new_rel_data.label}</div>`
  }

  function getMiniTree(d) {
    if (!props.mini_tree) return ''
    if (d.data.to_add) return ''
    if (d.data._new_rel_data) return ''
    if (d.all_rels_displayed) return ''
    return `<div class="mini-tree">${miniTreeSvgIcon()}</div>`
  }

  function cardInnerImageCircleRect(d) {
    return d.data.data.avatar ? cardInnerImageCircle(d) : cardInnerRect(d)
  }

  function cardInnerDefault(d) {
    return getCardInnerImageRect(d)
  }

  function cardInnerImageCircle(d) {
    return getCardInnerImageCircle(d)
  }

  function cardInnerImageRect(d) {
    return getCardInnerImageRect(d)
  }

  function cardInnerRect(d) {
    return getCardInnerRect(d)
  }

  function getClassList(d) {
    const class_list = [];
    if (d.data.data.gender === 'M') class_list.push('card-male');
    else if (d.data.data.gender === 'F') class_list.push('card-female');
    else class_list.push('card-genderless');

    if (d.data.main) class_list.push('card-main');

    if (d.data._new_rel_data) class_list.push('card-new-rel');

    if (d.data.to_add) class_list.push('card-to-add');

    return class_list
  }

  function getCardStyle() {
    let style = 'style="';
    if (props.card_dim.w || props.card_dim.h) {
      style += `width: ${props.card_dim.w}px; min-height: ${props.card_dim.h}px;`;
      if (props.card_dim.height_auto) style += 'height: auto;';
      else style += `height: ${props.card_dim.h}px;`;
    } else {
      return ''
    }
    style += '"';
    return style
  }

  function getCardImageStyle() {
    let style = 'style="position: relative;';
    if (props.card_dim.img_w || props.card_dim.img_h || props.card_dim.img_x || props.card_dim.img_y) {
      style += `width: ${props.card_dim.img_w}px; height: ${props.card_dim.img_h}px;`;
      style += `left: ${props.card_dim.img_x}px; top: ${props.card_dim.img_y}px;`;
    } else {
      return ''
    }
    style += '"';
    return style
  }

  function noImageIcon(d) {
    if (d.data._new_rel_data) return `<div class="person-icon" ${getCardImageStyle()}>${plusSvgIcon()}</div>`
    return `<div class="person-icon" ${getCardImageStyle()}>${personSvgIcon()}</div>`
  }
}

var elements = /*#__PURE__*/Object.freeze({
__proto__: null,
appendElement: appendElement,
Card: Card,
CardHtml: CardHtml
});

var addRelative = (...args) => { return new AddRelative(...args) };

function AddRelative(store, cancelCallback, onSubmitCallback) {
  this.store = store;

  this.cancelCallback = cancelCallback;
  this.onSubmitCallback = onSubmitCallback;

  this.datum = null;

  this.onChange = null;
  this.onCancel = null;

  this.is_active = false;
  this.store_data = null;

  this.addRelLabels = this.addRelLabelsDefault();

  return this
}

AddRelative.prototype.activate = function(datum) {
  if (this.is_active) this.onCancel();
  this.is_active = true;

  const store = this.store;

  this.store_data = store.getData();
  this.datum = datum;
  datum = JSON.parse(JSON.stringify(this.datum));

  const datum_rels = getDatumRelsData(datum, this.getStoreData(), this.addRelLabels);
  store.updateData(datum_rels);
  store.updateTree({});

  this.onChange = onChange.bind(this);
  this.onCancel = onCancel.bind(this);

  function onChange(updated_datum) {
    if (updated_datum?._new_rel_data) {
      const new_rel_datum = updated_datum;
      handleNewRel({datum: this.datum, new_rel_datum, data_stash: this.getStoreData()});
      this.onSubmitCallback(this.datum, new_rel_datum);
    } else if (updated_datum.id === this.datum.id) {
      this.datum.data = updated_datum.data;  // if in meanwhile the user changed the data for main datum, we need to keep it
    } else {
      console.error('Something went wrong');
    }
  }

  function onCancel() {
    if (!this.is_active) return
    this.is_active = false;

    store.updateData(this.getStoreData());
    this.cancelCallback(this.datum);

    this.store_data = null;
    this.datum = null;
    this.onChange = null;
    this.onCancel = null;
  }

};

AddRelative.prototype.setAddRelLabels = function(add_rel_labels) {
  if (typeof add_rel_labels !== 'object') {
    console.error('add_rel_labels must be an object');
    return
  }
  for (let key in add_rel_labels) {
    this.addRelLabels[key] = add_rel_labels[key];
  }
  return this
};

AddRelative.prototype.addRelLabelsDefault = function() {
  return {
    father: 'Add Father',
    mother: 'Add Mother',
    spouse: 'Add Spouse',
    son: 'Add Son',
    daughter: 'Add Daughter'
  }
};

AddRelative.prototype.getStoreData = function() {
  return this.store_data
};

function getDatumRelsData(datum, store_data, addRelLabels) {
  const datum_rels = getDatumRels(datum, store_data);

  if (!datum.rels.father) {
    const father = createNewPerson({data: {gender: "M"}, rels: {children: [datum.id]}});
    father._new_rel_data = {rel_type: "father", label: addRelLabels.father};
    datum.rels.father = father.id;
    datum_rels.push(father);
  }
  if (!datum.rels.mother) {
    const mother = createNewPerson({data: {gender: "F"}, rels: {children: [datum.id]}});
    mother._new_rel_data = {rel_type: "mother", label: addRelLabels.mother};
    datum.rels.mother = mother.id;
    datum_rels.push(mother);
  }
  const mother = datum_rels.find(d => d.id === datum.rels.mother);
  const father = datum_rels.find(d => d.id === datum.rels.father);
  mother.rels.spouses = [father.id];
  father.rels.spouses = [mother.id];

  mother.rels.children = [datum.id];
  father.rels.children = [datum.id];

  if (!datum.rels.spouses) datum.rels.spouses = [];

  if (datum.rels.children) {
    let new_spouse;
    datum.rels.children.forEach(child_id => {
      const child = datum_rels.find(d => d.id === child_id);
      if (!child.rels.mother) {
        if (!new_spouse) new_spouse = createNewPerson({data: {gender: "F"}, rels: {spouses: [datum.id], children: []}});
        new_spouse._new_rel_data = {rel_type: "spouse", label: addRelLabels.spouse};
        new_spouse.rels.children.push(child.id);
        datum.rels.spouses.push(new_spouse.id);
        child.rels.mother = new_spouse.id;
        datum_rels.push(new_spouse);
      }
      if (!child.rels.father) {
        if (!new_spouse) new_spouse = createNewPerson({data: {gender: "M"}, rels: {spouses: [datum.id], children: []}});
        new_spouse._new_rel_data = {rel_type: "spouse", label: addRelLabels.spouse};
        new_spouse.rels.children.push(child.id);
        datum.rels.spouses.push(new_spouse.id);
        child.rels.father = new_spouse.id;
        datum_rels.push(new_spouse);
      }
    });
  }

  const new_spouse = createNewPerson({data: {gender: "F"}, rels: {spouses: [datum.id]}});
  new_spouse._new_rel_data = {rel_type: "spouse", label: addRelLabels.spouse};
  datum.rels.spouses.push(new_spouse.id);
  datum_rels.push(new_spouse);

  if (!datum.rels.children) datum.rels.children = [];
  datum.rels.spouses.forEach(spouse_id => {
    const spouse = datum_rels.find(d => d.id === spouse_id);
    if (!spouse.rels.children) spouse.rels.children = [];
    spouse.rels.children = spouse.rels.children.filter(child_id => datum.rels.children.includes(child_id));
    
    const new_son = createNewPerson({data: {gender: "M"}, rels: {father: datum.id, mother: spouse.id}});
    new_son._new_rel_data = {rel_type: "son", label: addRelLabels.son, other_parent_id: spouse.id};
    spouse.rels.children.push(new_son.id);
    datum.rels.children.push(new_son.id);
    datum_rels.push(new_son);

    const new_daughter = createNewPerson({data: {gender: "F"}, rels: {mother: spouse.id, father: datum.id}});
    new_daughter._new_rel_data = {rel_type: "daughter", label: addRelLabels.daughter, other_parent_id: spouse.id};
    spouse.rels.children.push(new_daughter.id);
    datum.rels.children.push(new_daughter.id);
    datum_rels.push(new_daughter);
  });

  return datum_rels
}

function findRel(store_data, id) {
  return JSON.parse(JSON.stringify(store_data.find(d => d.id === id)))
}

function getDatumRels(datum, data) {
  const datum_rels = [datum];
  Object.keys(datum.rels).forEach(rel_type => {
    const rel = datum.rels[rel_type];
    if (Array.isArray(rel)) {
      rel.forEach(rel_id => {
        findAndPushRel(rel_type, rel_id);
      });
    } else {
      findAndPushRel(rel_type, rel);
    }
  });
  return datum_rels

  function findAndPushRel(rel_type, rel_id) {
    const rel_datum = findRel(data, rel_id);
    if (rel_type === 'father' || rel_type === 'mother') {
      delete rel_datum.rels.father;
      delete rel_datum.rels.mother;
    }

    if (rel_type === 'children') {
      rel_datum.rels.children = [];
      rel_datum.rels.spouses = [];
    }

    datum_rels.push(rel_datum);
  }
}

function editTree(...args) { return new EditTree(...args) }

function EditTree(cont, store) {
  this.cont = cont;
  this.store = store;

  this.fields = [
    {type: 'text', label: 'first name', id: 'first name'},
    {type: 'text', label: 'last name', id: 'last name'},
    {type: 'text', label: 'birthday', id: 'birthday'},
    {type: 'text', label: 'avatar', id: 'avatar'}
  ];

  this.form_cont = null;

  this.is_fixed = true;

  this.history = null;
  this.no_edit = false;

  this.onChange = null;

  this.editFirst = false;

  this.init();

  return this
}

EditTree.prototype.init = function() {
  this.form_cont = d3.select(this.cont).append('div').classed('f3-form-cont', true).node();
  this.addRelativeInstance = this.setupAddRelative();
  this.createHistory();
};

EditTree.prototype.open = function(datum) {
  if (datum.data.data) datum = datum.data;
  if (this.addRelativeInstance.is_active && !datum._new_rel_data) {
    this.addRelativeInstance.onCancel();
    datum = this.store.getDatum(datum.id);
  }

  this.cardEditForm(datum);
};

EditTree.prototype.openWithoutRelCancel = function(datum) {
  if (datum.data.data) datum = datum.data;

  this.cardEditForm(datum);
};

EditTree.prototype.cardEditForm = function(datum) {
  const props = {};
  const is_new_rel = datum?._new_rel_data;
  if (is_new_rel) {
    props.onCancel = () => this.addRelativeInstance.onCancel();
  } else {
    props.addRelative = this.addRelativeInstance;
    props.deletePerson = () => {
      const data = this.store.getData();
      deletePerson(datum, data);
      this.store.updateData(data);
      this.openFormWithId(this.store.getLastAvailableMainDatum().id);

      this.store.updateTree({});
    };
  }

  const form_creator = f3.handlers.createForm({
    store: this.store, 
    datum, 
    postSubmit: postSubmit.bind(this),
    fields: this.fields, 
    card_display: this.card_display, 
    addRelative: null,
    onCancel: () => {},
    editFirst: this.editFirst,
    ...props
  });

  form_creator.no_edit = this.no_edit;
  const form_cont = f3.handlers.formInfoSetup(form_creator, this.closeForm.bind(this));

  this.form_cont.innerHTML = '';
  this.form_cont.appendChild(form_cont);

  this.openForm();

  function postSubmit(props) {
    if (this.addRelativeInstance.is_active) this.addRelativeInstance.onChange(datum);
    else if (!props?.delete) this.openFormWithId(datum.id);

    if (!this.is_fixed) this.closeForm();
    
    this.store.updateTree({});

    this.updateHistory();
  }
};

EditTree.prototype.openForm = function() {
  d3.select(this.form_cont).classed('opened', true);
};

EditTree.prototype.closeForm = function() {
  d3.select(this.form_cont).classed('opened', false).html('');
  this.store.updateTree({});
};

EditTree.prototype.fixed = function() {
  this.is_fixed = true;
  d3.select(this.form_cont).style('position', 'relative');

  return this
};

EditTree.prototype.absolute = function() {
  this.is_fixed = false;
  d3.select(this.form_cont).style('position', 'absolute');

  return this
};

EditTree.prototype.setCardClickOpen = function(card) {
  card.setOnCardClick((e, d) => {
    if (this.addRelativeInstance.is_active) {
      this.open(d);
      return
    }
    this.open(d);
    this.store.updateMainId(d.data.id);
    this.store.updateTree({});
  });

  return this
};

EditTree.prototype.openFormWithId = function(d_id) {
  if (d_id) {
    const d = this.store.getDatum(d_id);
    this.openWithoutRelCancel({data: d});
  } else {
    const d = this.store.getMainDatum();
    this.openWithoutRelCancel({data: d});
  }
};

EditTree.prototype.createHistory = function() {
  this.history = f3.handlers.createHistory(this.store, this.getStoreData.bind(this), historyUpdateTree.bind(this));
  this.history.controls = f3.handlers.createHistoryControls(this.cont, this.history);
  this.history.changed();
  this.history.controls.updateButtons();

  return this

  function historyUpdateTree() {
    if (this.addRelativeInstance.is_active) this.addRelativeInstance.onCancel();
    this.store.updateTree({initial: false});
    this.history.controls.updateButtons();
    this.openFormWithId(this.store.getMainDatum()?.id);
  }
};

EditTree.prototype.setNoEdit = function() {
  this.no_edit = true;

  return this
};

EditTree.prototype.setEdit = function() {
  this.no_edit = false;

  return this
};

EditTree.prototype.setFields = function(fields) {
  const new_fields = [];
  if (!Array.isArray(fields)) {
    console.error('fields must be an array');
    return this
  }
  for (const field of fields) {
    if (typeof field === 'string') {
      new_fields.push({type: 'text', label: field, id: field});
    } else if (typeof field === 'object') {
      if (!field.id) {
        console.error('fields must be an array of objects with id property');
      } else {
        new_fields.push(field);
      }
    } else {
      console.error('fields must be an array of strings or objects');
    }
  }
  this.fields = new_fields;

  return this
};

EditTree.prototype.setOnChange = function(fn) {
  this.onChange = fn;

  return this
};

EditTree.prototype.addRelative = function(datum) {
  if (!datum) datum = this.store.getMainDatum();
  this.addRelativeInstance.activate(datum);

  return this

};

EditTree.prototype.setupAddRelative = function() {
  return addRelative(this.store, cancelCallback.bind(this), onSubmitCallback.bind(this))

  function onSubmitCallback(datum, new_rel_datum) {
    this.store.updateMainId(datum.id);
    this.openFormWithId(datum.id);
  }

  function cancelCallback(datum) {
    this.store.updateMainId(datum.id);
    this.store.updateTree({});
    this.openFormWithId(datum.id);
  }
};

EditTree.prototype.setEditFirst = function(editFirst) {
  this.editFirst = editFirst;

  return this
};

EditTree.prototype.isAddingRelative = function() {
  return this.addRelativeInstance.is_active
};

EditTree.prototype.setAddRelLabels = function(add_rel_labels) {
  this.addRelativeInstance.setAddRelLabels(add_rel_labels);
  return this
};

EditTree.prototype.getStoreData = function() {
  if (this.addRelativeInstance.is_active) return this.addRelativeInstance.getStoreData()
  else return this.store.getData()
};

EditTree.prototype.getDataJson = function(fn) {
  const data = this.getStoreData();
  return f3.handlers.cleanupDataJson(JSON.stringify(data))
};

EditTree.prototype.updateHistory = function() {
  if (this.history) {
    this.history.changed();
    this.history.controls.updateButtons();
  }

  if (this.onChange) this.onChange();
};



EditTree.prototype.destroy = function() {
  this.history.controls.destroy();
  this.history = null;
  d3.select(this.cont).select('.f3-form-cont').remove();
  if (this.addRelativeInstance.onCancel) this.addRelativeInstance.onCancel();
  this.store.updateTree({});

  return this
};

function createChart(...args) { return new CreateChart(...args) }

function CreateChart(cont, data) {
  this.cont = null;
  this.store = null;
  this.svg = null;
  this.getCard = null;
  this.node_separation = 250;
  this.level_separation = 150;
  this.is_horizontal = false;
  this.single_parent_empty_card = true;
  this.transition_time = 2000;

  this.is_card_html = false;

  this.beforeUpdate = null;
  this.afterUpdate = null;

  this.init(cont, data);

  return this
}

CreateChart.prototype.init = function(cont, data) {
  this.cont = cont = setCont(cont);
  const getSvgView = () => cont.querySelector('svg .view');
  const getHtmlSvg = () => cont.querySelector('#htmlSvg');
  const getHtmlView = () => cont.querySelector('#htmlSvg .cards_view');

  this.svg = f3.createSvg(cont, {onZoom: f3.htmlHandlers.onZoomSetup(getSvgView, getHtmlView)});
  f3.htmlHandlers.createHtmlSvg(cont);

  this.store = f3.createStore({
    data,
    node_separation: this.node_separation,
    level_separation: this.level_separation,
    single_parent_empty_card: this.single_parent_empty_card,
    is_horizontal: this.is_horizontal
  });

  this.setCard(f3.CardSvg); // set default card

  this.store.setOnUpdate(props => {
    if (this.beforeUpdate) this.beforeUpdate(props);
    props = Object.assign({transition_time: this.transition_time}, props || {});
    if (this.is_card_html) props = Object.assign({}, props || {}, {cardHtml: getHtmlSvg()});
    f3.view(this.store.getTree(), this.svg, this.getCard(), props || {});
    if (this.afterUpdate) this.afterUpdate(props);
  });
};

CreateChart.prototype.updateTree = function(props = {initial: false}) {
  this.store.updateTree(props);

  return this
};

CreateChart.prototype.updateData = function(data) {
  this.store.updateData(data);

  return this
};

CreateChart.prototype.setCardYSpacing = function(card_y_spacing) {
  if (typeof card_y_spacing !== 'number') {
    console.error('card_y_spacing must be a number');
    return this
  }
  this.level_separation = card_y_spacing;
  this.store.state.level_separation = card_y_spacing;

  return this
};

CreateChart.prototype.setCardXSpacing = function(card_x_spacing) {
  if (typeof card_x_spacing !== 'number') {
    console.error('card_x_spacing must be a number');
    return this
  }
  this.node_separation = card_x_spacing;
  this.store.state.node_separation = card_x_spacing;

  return this
};

CreateChart.prototype.setOrientationVertical = function() {
  this.is_horizontal = false;
  this.store.state.is_horizontal = false;

  return this
};

CreateChart.prototype.setOrientationHorizontal = function() {
  this.is_horizontal = true;
  this.store.state.is_horizontal = true;

  return this
};

CreateChart.prototype.setSingleParentEmptyCard = function(single_parent_empty_card, {label='Unknown'} = {}) {
  this.single_parent_empty_card = single_parent_empty_card;
  this.store.state.single_parent_empty_card = single_parent_empty_card;
  this.store.state.single_parent_empty_card_label = label;
  if (this.editTreeInstance && this.editTreeInstance.addRelativeInstance.is_active) this.editTreeInstance.addRelativeInstance.onCancel();
  f3.handlers.removeToAddFromData(this.store.getData() || []);

  return this
};


CreateChart.prototype.setCard = function(Card) {
  this.is_card_html = Card.is_html;

  if (this.is_card_html) {
    this.svg.querySelector('.cards_view').innerHTML = '';
    this.cont.querySelector('#htmlSvg').style.display = 'block';
  } else {
    this.cont.querySelector('#htmlSvg .cards_view').innerHTML = '';
    this.cont.querySelector('#htmlSvg').style.display = 'none';
  }

  const card = Card(this.cont, this.store);
  this.getCard = () => card.getCard();

  return card
};

CreateChart.prototype.setTransitionTime = function(transition_time) {
  this.transition_time = transition_time;

  return this
};

CreateChart.prototype.editTree = function() {
  return this.editTreeInstance = editTree(this.cont, this.store)
};

CreateChart.prototype.updateMain = function(d) {
  this.store.updateMainId(d.data.id);
  this.store.updateTree({});

  return this
};

CreateChart.prototype.updateMainId = function(id) {
  this.store.updateMainId(id);

  return this
};

CreateChart.prototype.getMainDatum = function() {
  return this.store.getMainDatum()
};

CreateChart.prototype.getDataJson = function(fn) {
  const data = this.store.getData();
  return f3.handlers.cleanupDataJson(JSON.stringify(data))
};

CreateChart.prototype.updateData = function(data) {
  this.store.updateData(data);
};

CreateChart.prototype.setBeforeUpdate = function(fn) {
  this.beforeUpdate = fn;
  return this
};

CreateChart.prototype.setAfterUpdate = function(fn) {
  this.afterUpdate = fn;
  return this
};

function setCont(cont) {
  if (typeof cont === "string") cont = document.querySelector(cont);
  return cont
}

function processCardDisplay(card_display) {
  const card_display_arr = [];
  if (Array.isArray(card_display)) {
    card_display.forEach(d => {
      if (typeof d === 'function') {
        card_display_arr.push(d);
      } else if (typeof d === 'string') {
        card_display_arr.push(d1 => d1.data[d]);
      } else if (Array.isArray(d)) {
        card_display_arr.push(d1 => d.map(d2 => d1.data[d2]).join(' '));
      }
    });
  } else if (typeof card_display === 'function') {
    card_display_arr.push(card_display);
  } else if (typeof card_display === 'string') {
    card_display_arr.push(d1 => d1.data[card_display]);
  }
  return card_display_arr
}

CardSvgWrapper.is_html = false;
function CardSvgWrapper(...args) { return new CardSvg(...args) }

function CardSvg(cont, store) {
  this.cont = cont;
  this.store = store;
  this.svg = null;
  this.getCard = null;
  this.card_dim = {w:220,h:70,text_x:75,text_y:15,img_w:60,img_h:60,img_x:5,img_y:5};
  this.card_display = [d => `${d.data["first name"]} ${d.data["last name"]}`];
  this.mini_tree = true;
  this.link_break = false;
  this.onCardClick = this.onCardClickDefault;
  this.onCardUpdate = null;
  this.onCardUpdates = null;

  this.init();

  return this
}

CardSvg.prototype.init = function() {
  this.svg = this.cont.querySelector('svg.main_svg');

  this.getCard = () => f3.elements.Card({
    store: this.store,
    svg: this.svg,
    card_dim: this.card_dim,
    card_display: this.card_display,
    mini_tree: this.mini_tree,
    link_break: this.link_break,
    onCardClick: this.onCardClick,
    onCardUpdate: this.onCardUpdate,
    onCardUpdates: this.onCardUpdates
  });
};

CardSvg.prototype.setCardDisplay = function(card_display) {
  this.card_display = processCardDisplay(card_display);

  return this
};

CardSvg.prototype.setCardDim = function(card_dim) {
  if (typeof card_dim !== 'object') {
    console.error('card_dim must be an object');
    return this
  }
  for (let key in card_dim) {
    const val = card_dim[key];
    if (typeof val !== 'number') {
      console.error(`card_dim.${key} must be a number`);
      return this
    }
    if (key === 'width') key = 'w';
    if (key === 'height') key = 'h';
    this.card_dim[key] = val;
  }

  updateCardSvgDefs(this.svg, this.card_dim);

  return this
};

CardSvg.prototype.setMiniTree = function(mini_tree) {
  this.mini_tree = mini_tree;

  return this
};

CardSvg.prototype.setLinkBreak = function(link_break) {
  this.link_break = link_break;

  return this
};

CardSvg.prototype.setCardTextSvg = function(cardTextSvg) {
  function onCardUpdate(d) {
    const card_node = d3.select(this);
    const card_text = card_node.select('.card-text text');
    const card_text_g = card_text.node().parentNode;
    card_text_g.innerHTML = cardTextSvg(d.data);
  }
  onCardUpdate.id = 'setCardTextSvg';
  if (!this.onCardUpdates) this.onCardUpdates = [];
  this.onCardUpdates = this.onCardUpdates.filter(fn => fn.id !== 'setCardTextSvg');
  this.onCardUpdates.push(onCardUpdate);

  return this
};

CardSvg.prototype.onCardClickDefault = function(e, d) {
  this.store.updateMainId(d.data.id);
  this.store.updateTree({});
};

CardSvg.prototype.setOnCardClick = function(onCardClick) {
  this.onCardClick = onCardClick;

  return this
};

CardHtmlWrapper.is_html = true;
function CardHtmlWrapper(...args) { return new CardHtml$1(...args) }

CardHtml$1.prototype.is_html = true;
function CardHtml$1(cont, store) {
  this.cont = cont;
  this.store = store;
  this.getCard = null;
  this.card_display = [d => `${d.data["first name"]} ${d.data["last name"]}`];
  this.onCardClick = this.onCardClickDefault;
  this.style = 'default';
  this.mini_tree = false;
  this.onCardUpdate = null;
  this.card_dim = {};

  this.init();

  return this
}

CardHtml$1.prototype.init = function() {
  this.svg = this.cont.querySelector('svg.main_svg');

  this.getCard = () => f3.elements.CardHtml({
    store: this.store,
    card_display: this.card_display,
    onCardClick: this.onCardClick,
    style: this.style,
    mini_tree: this.mini_tree,
    onCardUpdate: this.onCardUpdate,
    card_dim: this.card_dim,
    empty_card_label: this.store.state.single_parent_empty_card_label,
    onCardMouseenter: this.onCardMouseenter ? this.onCardMouseenter.bind(this) : null,
    onCardMouseleave: this.onCardMouseleave ? this.onCardMouseleave.bind(this) : null
  });
};

CardHtml$1.prototype.setCardDisplay = function(card_display) {
  this.card_display = processCardDisplay(card_display);

  return this
};

CardHtml$1.prototype.setOnCardClick = function(onCardClick) {
  this.onCardClick = onCardClick;
  return this
};

CardHtml$1.prototype.onCardClickDefault = function(e, d) {
  this.store.updateMainId(d.data.id);
  this.store.updateTree({});
};

CardHtml$1.prototype.setStyle = function(style) {
  this.style = style;
  return this
};

CardHtml$1.prototype.setMiniTree = function(mini_tree) {
  this.mini_tree = mini_tree;

  return this
};

CardHtml$1.prototype.setOnCardUpdate = function(onCardUpdate) {
  this.onCardUpdate = onCardUpdate;
  return this
};

CardHtml$1.prototype.setCardDim = function(card_dim) {
  if (typeof card_dim !== 'object') {
    console.error('card_dim must be an object');
    return this
  }
  for (let key in card_dim) {
    const val = card_dim[key];
    if (typeof val !== 'number' && typeof val !== 'boolean') {
      console.error(`card_dim.${key} must be a number or boolean`);
      return this
    }
    if (key === 'width') key = 'w';
    if (key === 'height') key = 'h';
    if (key === 'img_width') key = 'img_w';
    if (key === 'img_height') key = 'img_h';
    if (key === 'img_x') key = 'img_x';
    if (key === 'img_y') key = 'img_y';
    this.card_dim[key] = val;
  }

  return this
};

CardHtml$1.prototype.resetCardDim = function() {
  this.card_dim = {};
  return this
};

CardHtml$1.prototype.setOnHoverPathToMain = function() {
  this.onCardMouseenter = this.onEnterPathToMain.bind(this);
  this.onCardMouseleave = this.onLeavePathToMain.bind(this);
  return this
};

CardHtml$1.prototype.unsetOnHoverPathToMain = function() {
  this.onCardMouseenter = null;
  this.onCardMouseleave = null;
  return this
};

CardHtml$1.prototype.onEnterPathToMain = function(e, datum) {
  this.to_transition = datum.data.id;
  const main_datum = this.store.getTreeMainDatum();
  const cards = d3.select(this.cont).select('div.cards_view').selectAll('.card_cont');
  const links = d3.select(this.cont).select('svg.main_svg .links_view').selectAll('.link');
  const [cards_node_to_main, links_node_to_main] = pathToMain(cards, links, datum, main_datum);
  cards_node_to_main.forEach(d => {
    const delay = Math.abs(datum.depth - d.card.depth) * 200;
    d3.select(d.node.querySelector('div.card-inner'))
      .transition().duration(0).delay(delay)
      .on('end', () => this.to_transition === datum.data.id && d3.select(d.node.querySelector('div.card-inner')).classed('f3-path-to-main', true));
  });
  links_node_to_main.forEach(d => {
    const delay = Math.abs(datum.depth - d.link.depth) * 200;
    d3.select(d.node)
      .transition().duration(0).delay(delay)
      .on('end', () => this.to_transition === datum.data.id && d3.select(d.node).classed('f3-path-to-main', true));
  });

  return this
};

CardHtml$1.prototype.onLeavePathToMain = function(e, d) {
  this.to_transition = false;
  d3.select(this.cont).select('div.cards_view').selectAll('div.card-inner').classed('f3-path-to-main', false);
  d3.select(this.cont).select('svg.main_svg .links_view').selectAll('.link').classed('f3-path-to-main', false);

  return this
};

var f3 = {
  CalculateTree,
  createStore,
  view,
  createSvg,
  handlers,
  elements,
  htmlHandlers,
  icons,
  createChart,

  CardSvg: CardSvgWrapper,
  CardHtml: CardHtmlWrapper,
};

return f3;

})));
